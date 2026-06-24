"""Agent and feature parity checker.

Compares local QlikToPowerBI agent and feature inventory with:
1) local required baseline checks, and
2) optional upstream repository checks (TableauToPowerBI candidate).

Usage examples:
  py -3 tools/analysis/agent_feature_parity_check.py
  py -3 tools/analysis/agent_feature_parity_check.py --upstream-repo owner/repo
    py -3 tools/analysis/agent_feature_parity_check.py --upstream-path "C:/GitHub Project/TableauToPowerBI"
  py -3 tools/analysis/agent_feature_parity_check.py --upstream-repo owner/repo --json
    py -3 tools/analysis/agent_feature_parity_check.py --scan-default-candidates
"""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.error
import urllib.request
from pathlib import Path


REQUIRED_AGENT_FILES = [
    "assessor.agent.md",
    "converter.agent.md",
    "dax.agent.md",
    "deployer.agent.md",
    "extractor.agent.md",
    "generator.agent.md",
    "merger.agent.md",
    "orchestrator.agent.md",
    "preceptor.agent.md",
    "reviewer.agent.md",
    "semantic.agent.md",
    "shared.instructions.md",
    "tester.agent.md",
    "visual.agent.md",
    "wiring.agent.md",
]

REQUIRED_MODULES = [
    "powerbi_import/preceptor.py",
    "powerbi_import/self_healing_v3.py",
    "powerbi_import/repair_strategies.py",
    "powerbi_import/self_healing_report.py",
    "powerbi_import/cutover_manager.py",
    "powerbi_import/full_lineage.py",
    "powerbi_import/pdf_renderer.py",
    "powerbi_import/pptx_report.py",
    "powerbi_import/report_packager.py",
    "powerbi_import/goals_generator.py",
    "powerbi_import/script_lineage.py",
    "powerbi_import/script_lineage_report.py",
    "powerbi_import/automation.py",
]

REQUIRED_FLAGS = [
    "--preceptor-review",
    "--self-heal-v3",
    "--repair-strategies",
    "--cutover-plan",
    "--full-lineage",
    "--pdf-report",
    "--pptx-report",
    "--package",
    "--goals",
    "--script-lineage",
]

DEFAULT_CANDIDATE_REPOS = [
    "anvssajay17/tableautopowerbi",
    "agarwv/TableauToPowerBI",
    "Mourya0/TableauToPowerBi",
    "mjkeeplearning-source/tableauToPowerBI",
    "Shreyagattikoppula/tableautopowerbi_backend",
]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def fetch_raw(repo: str, branch: str, rel_path: str, timeout: float = 10.0) -> tuple[bool, str | None]:
    url = f"https://raw.githubusercontent.com/{repo}/{branch}/{rel_path}"
    req = urllib.request.Request(url, headers={"User-Agent": "QlikToPowerBI-parity-check/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return True, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError:
        return False, None
    except Exception:
        return False, None


def fetch_local(base_path: Path, rel_path: str) -> tuple[bool, str | None]:
    try:
        target = (base_path / rel_path).resolve()
        if not target.exists() or not target.is_file():
            return False, None
        return True, target.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return False, None


def fetch_from_source(
    source_kind: str,
    source_id: str,
    branch: str,
    rel_path: str,
) -> tuple[bool, str | None]:
    if source_kind == "repo":
        return fetch_raw(source_id, branch, rel_path)
    if source_kind == "path":
        return fetch_local(Path(source_id), rel_path)
    return False, None


def load_candidate_repos(candidate_file: Path | None) -> list[str]:
    if candidate_file is None:
        return []
    if not candidate_file.exists():
        return []
    items = []
    for line in candidate_file.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        items.append(raw)
    return items


def check_local_agents(repo_root: Path) -> dict:
    agents_dir = repo_root / ".github" / "agents"
    existing = sorted(p.name for p in agents_dir.glob("*.md"))
    missing = [name for name in REQUIRED_AGENT_FILES if name not in existing]
    return {
        "check": "local_agents",
        "required_count": len(REQUIRED_AGENT_FILES),
        "existing_count": len(existing),
        "missing": missing,
        "ok": len(missing) == 0,
    }


def check_local_features(repo_root: Path) -> dict:
    missing_modules = [rel for rel in REQUIRED_MODULES if not (repo_root / rel).exists()]

    migrate_path = repo_root / "migrate.py"
    migrate_text = read_text(migrate_path)
    missing_flags = [flag for flag in REQUIRED_FLAGS if flag not in migrate_text]

    return {
        "check": "local_features",
        "missing_modules": missing_modules,
        "missing_flags": missing_flags,
        "ok": len(missing_modules) == 0 and len(missing_flags) == 0,
    }


def check_upstream_agents(
    repo_root: Path,
    source_kind: str,
    source_id: str,
    branch: str,
) -> dict:
    local_dir = repo_root / ".github" / "agents"

    present_upstream = []
    missing_upstream = []
    hash_equal = []
    hash_different = []

    for name in REQUIRED_AGENT_FILES:
        rel = f".github/agents/{name}"
        local_text = read_text(local_dir / name)
        ok, upstream_text = fetch_from_source(source_kind, source_id, branch, rel)
        if not ok or upstream_text is None:
            missing_upstream.append(rel)
            continue

        present_upstream.append(rel)
        if sha256_text(local_text) == sha256_text(upstream_text):
            hash_equal.append(rel)
        else:
            hash_different.append(rel)

    return {
        "check": "upstream_agents",
        "source_kind": source_kind,
        "source_id": source_id,
        "branch": branch,
        "required_count": len(REQUIRED_AGENT_FILES),
        "present_upstream": present_upstream,
        "missing_upstream": missing_upstream,
        "hash_equal": hash_equal,
        "hash_different": hash_different,
        "present_count": len(present_upstream),
        "coverage": len(present_upstream) / float(len(REQUIRED_AGENT_FILES)),
        "ok": len(missing_upstream) == 0,
    }


def check_upstream_features(source_kind: str, source_id: str, branch: str) -> dict:
    missing_modules = []

    for rel in REQUIRED_MODULES:
        ok, _ = fetch_from_source(source_kind, source_id, branch, rel)
        if not ok:
            missing_modules.append(rel)

    ok_migrate, migrate_text = fetch_from_source(source_kind, source_id, branch, "migrate.py")
    missing_flags = []
    if ok_migrate and migrate_text is not None:
        missing_flags = [flag for flag in REQUIRED_FLAGS if flag not in migrate_text]
    else:
        missing_flags = REQUIRED_FLAGS.copy()

    present_modules = len(REQUIRED_MODULES) - len(missing_modules)
    present_flags = len(REQUIRED_FLAGS) - len(missing_flags)
    module_coverage = present_modules / float(len(REQUIRED_MODULES))
    flag_coverage = present_flags / float(len(REQUIRED_FLAGS))

    return {
        "check": "upstream_features",
        "source_kind": source_kind,
        "source_id": source_id,
        "branch": branch,
        "required_modules_count": len(REQUIRED_MODULES),
        "required_flags_count": len(REQUIRED_FLAGS),
        "present_modules_count": present_modules,
        "present_flags_count": present_flags,
        "module_coverage": module_coverage,
        "flag_coverage": flag_coverage,
        "missing_modules": missing_modules,
        "missing_flags": missing_flags,
        "ok": len(missing_modules) == 0 and len(missing_flags) == 0,
    }


def check_single_upstream(
    repo_root: Path,
    source_kind: str,
    source_id: str,
    branch: str,
) -> dict:
    agents = check_upstream_agents(repo_root, source_kind, source_id, branch)
    features = check_upstream_features(source_kind, source_id, branch)

    # Weighted score: agents 50%, modules 30%, flags 20%
    score = (
        agents["coverage"] * 0.50
        + features["module_coverage"] * 0.30
        + features["flag_coverage"] * 0.20
    )

    return {
        "source_kind": source_kind,
        "source_id": source_id,
        "source_label": f"{source_kind}:{source_id}",
        "branch": branch,
        "agents": agents,
        "features": features,
        "score": score,
        "ok": agents["ok"] and features["ok"],
    }


def build_report(
    repo_root: Path,
    upstream_sources: list[dict],
    branch: str,
    strict_upstream: bool,
) -> dict:
    results = [
        check_local_agents(repo_root),
        check_local_features(repo_root),
    ]

    upstream_results = []
    for source in upstream_sources:
        upstream_results.append(
            check_single_upstream(
                repo_root,
                source["kind"],
                source["id"],
                branch,
            )
        )

    upstream_results_sorted = sorted(upstream_results, key=lambda r: r["score"], reverse=True)
    best_match = upstream_results_sorted[0] if upstream_results_sorted else None

    local_ok = all(r.get("ok", False) for r in results)
    upstream_ok = all(r.get("ok", False) for r in upstream_results_sorted) if upstream_results_sorted else True
    all_ok = local_ok and (upstream_ok if strict_upstream else True)

    return {
        "repo": str(repo_root),
        "upstream_sources": upstream_sources,
        "branch": branch,
        "strict_upstream": strict_upstream,
        "local_ok": local_ok,
        "upstream_ok": upstream_ok,
        "all_ok": all_ok,
        "results": results,
        "upstream_results": upstream_results_sorted,
        "best_match": best_match,
    }


def print_human(report: dict) -> None:
    print("Agent + Feature Parity Check")
    print("============================")
    print(f"Repository: {report['repo']}")
    if report["upstream_sources"]:
        print(f"Upstream candidates: {len(report['upstream_sources'])} ({report['branch']})")
    print(f"Local checks: {'PASS' if report['local_ok'] else 'FAIL'}")
    print(f"Upstream strict mode: {'ON' if report['strict_upstream'] else 'OFF'}")
    print(f"Overall: {'PASS' if report['all_ok'] else 'FAIL'}")

    for result in report["results"]:
        name = result["check"]
        status = "PASS" if result.get("ok") else "FAIL"
        print(f"\n[{status}] {name}")

        if name == "local_agents":
            print(f"  required_count: {result['required_count']}")
            print(f"  existing_count: {result['existing_count']}")
            if result["missing"]:
                print("  missing:")
                for item in result["missing"]:
                    print(f"  - {item}")
            else:
                print("  missing: none")

        if name in {"local_features", "upstream_features"}:
            if result["missing_modules"]:
                print("  missing_modules:")
                for item in result["missing_modules"]:
                    print(f"  - {item}")
            else:
                print("  missing_modules: none")

            if result["missing_flags"]:
                print("  missing_flags:")
                for item in result["missing_flags"]:
                    print(f"  - {item}")
            else:
                print("  missing_flags: none")

    if report["upstream_results"]:
        print("\nUpstream ranking")
        print("----------------")
        for idx, upstream in enumerate(report["upstream_results"], start=1):
            agents = upstream["agents"]
            features = upstream["features"]
            print(
                f"{idx}. {upstream['source_label']}"
                f" score={upstream['score']:.3f}"
                f" agents={agents['present_count']}/{agents['required_count']}"
                f" modules={features['present_modules_count']}/{features['required_modules_count']}"
                f" flags={features['present_flags_count']}/{features['required_flags_count']}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Check local and upstream agent/feature parity")
    parser.add_argument("--repo-root", default=".", help="Repository root path")
    parser.add_argument(
        "--upstream-repo",
        action="append",
        default=[],
        help="Optional upstream repo in owner/repo format for remote parity checks",
    )
    parser.add_argument(
        "--upstream-path",
        action="append",
        default=[],
        help="Optional local upstream repository path for filesystem-based parity checks",
    )
    parser.add_argument(
        "--scan-default-candidates",
        action="store_true",
        default=False,
        help="Also scan built-in TableauToPowerBI candidate repositories",
    )
    parser.add_argument(
        "--candidate-file",
        default=None,
        help="Path to a file containing candidate owner/repo values (one per line)",
    )
    parser.add_argument("--branch", default="main", help="Upstream branch name")
    parser.add_argument(
        "--strict-upstream",
        action="store_true",
        default=False,
        help="Fail exit code if any selected upstream candidate is not fully at parity",
    )
    parser.add_argument("--json", action="store_true", default=False, help="Emit JSON")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()

    candidate_file = Path(args.candidate_file).resolve() if args.candidate_file else None
    candidate_repos = []
    candidate_repos.extend(args.upstream_repo)
    candidate_repos.extend(load_candidate_repos(candidate_file))
    if args.scan_default_candidates:
        candidate_repos.extend(DEFAULT_CANDIDATE_REPOS)

    # de-duplicate while preserving order
    deduped = []
    seen = set()
    for repo in candidate_repos:
        key = repo.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(key)

    deduped_paths = []
    seen_paths = set()
    for raw in args.upstream_path:
        key = str(Path(raw).resolve())
        if key in seen_paths:
            continue
        seen_paths.add(key)
        deduped_paths.append(key)

    upstream_sources = []
    for repo in deduped:
        upstream_sources.append({"kind": "repo", "id": repo})
    for path_item in deduped_paths:
        upstream_sources.append({"kind": "path", "id": path_item})

    report = build_report(repo_root, upstream_sources, args.branch, args.strict_upstream)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_human(report)

    return 0 if report["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
