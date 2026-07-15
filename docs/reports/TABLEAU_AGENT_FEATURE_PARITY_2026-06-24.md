<!-- DOC-SHINY-BANNER -->
![Documentation](https://img.shields.io/badge/Documentation-Shiny_Style-0A66C2?style=flat-square&logo=readthedocs&logoColor=white)
![Maintained](https://img.shields.io/badge/Maintained-2026-2EA44F?style=flat-square&logo=github&logoColor=white)
![Navigation](https://img.shields.io/badge/Navigation-Quick_Access-6F42C1?style=flat-square&logo=bookstack&logoColor=white)
# TableauToPowerBI Agent and Feature Parity Report (2026-06-24)

## Objective

Establish a repeatable parity process between this repository and TableauToPowerBI for:
- agent-side architecture and responsibilities
- migration feature surface (modules + CLI flags)

## Local Baseline (QlikToPowerBI)

### Agent inventory present

The following local agent definitions exist under `.github/agents/`:

- assessor.agent.md
- converter.agent.md
- dax.agent.md
- deployer.agent.md
- extractor.agent.md
- generator.agent.md
- merger.agent.md
- orchestrator.agent.md
- preceptor.agent.md
- reviewer.agent.md
- semantic.agent.md
- shared.instructions.md
- tester.agent.md
- visual.agent.md
- wiring.agent.md

### Feature baseline used for parity checks

Modules:
- powerbi_import/preceptor.py
- powerbi_import/self_healing_v3.py
- powerbi_import/repair_strategies.py
- powerbi_import/self_healing_report.py
- powerbi_import/cutover_manager.py
- powerbi_import/full_lineage.py
- powerbi_import/pdf_renderer.py
- powerbi_import/pptx_report.py
- powerbi_import/report_packager.py
- powerbi_import/goals_generator.py
- powerbi_import/script_lineage.py
- powerbi_import/script_lineage_report.py
- powerbi_import/automation.py

CLI flags:
- --preceptor-review
- --self-heal-v3
- --repair-strategies
- --cutover-plan
- --full-lineage
- --pdf-report
- --pptx-report
- --package
- --goals
- --script-lineage

## Upstream Retrieval Status

Authoritative upstream path provided and validated:

- `C:/GitHub Project/TableauToPowerBI`

Parity checks below use this local upstream repository as source of truth.

### Executed candidate check (sample)

Command executed:

```bash
py -3 tools/analysis/agent_feature_parity_check.py --upstream-repo anvssajay17/tableautopowerbi --json
```

Observed result summary:

- `local_agents`: PASS
- `local_features`: PASS
- `upstream_agents`: FAIL (0/15 required agent files present at expected paths)
- `upstream_features`: FAIL (required v12 module and flag baseline not present)

Interpretation:

- The candidate repository does not appear to be a feature-equivalent upstream for
	this project's current agent/feature baseline.
- A canonical TableauToPowerBI upstream still needs explicit confirmation for
	authoritative parity claims.

### Executed authoritative local-path check

Command executed:

```bash
py -3 tools/analysis/agent_feature_parity_check.py --upstream-path "C:/GitHub Project/TableauToPowerBI" --json
```

Observed result summary:

- Upstream score: `0.757`
- Agent coverage: `14/15` (93.33%)
- Module coverage: `10/13` (76.92%)
- Flag coverage: `3/10` (30.00%)

Missing upstream agent file:

- `.github/agents/preceptor.agent.md`

Missing upstream modules:

- `powerbi_import/script_lineage.py`
- `powerbi_import/script_lineage_report.py`
- `powerbi_import/automation.py`

Missing upstream flags:

- `--preceptor-review`
- `--self-heal-v3`
- `--repair-strategies`
- `--pdf-report`
- `--pptx-report`
- `--package`
- `--script-lineage`

Interpretation:

- Agent-side parity is near-complete but lacks the preceptor role file.
- Feature parity is partial; upstream is missing several v12 hardening/reporting
  capabilities compared with this repository baseline.

### Executed candidate scan (multi-repo)

Command executed:

```bash
py -3 tools/analysis/agent_feature_parity_check.py --scan-default-candidates
```

Ranked results:

1. `anvssajay17/tableautopowerbi` - score 0.000 (agents 0/15, modules 0/13, flags 0/10)
2. `agarwv/TableauToPowerBI` - score 0.000 (agents 0/15, modules 0/13, flags 0/10)
3. `Mourya0/TableauToPowerBi` - score 0.000 (agents 0/15, modules 0/13, flags 0/10)
4. `mjkeeplearning-source/tableauToPowerBI` - score 0.000 (agents 0/15, modules 0/13, flags 0/10)
5. `Shreyagattikoppula/tableautopowerbi_backend` - score 0.000 (agents 0/15, modules 0/13, flags 0/10)

Conclusion:

- None of the scanned public candidates currently expose the expected
	`.github/agents/*` and migration feature baseline for parity.
- Direct upstream parity remains blocked until the canonical upstream repository
	is provided.

## New Automated Parity Workflow

A dedicated script has been added:
- tools/analysis/agent_feature_parity_check.py

### Local-only parity check

```bash
py -3 tools/analysis/agent_feature_parity_check.py
```

### Local + upstream parity check

```bash
py -3 tools/analysis/agent_feature_parity_check.py --upstream-repo OWNER/REPO --branch main
```

### Multi-candidate parity scan

```bash
py -3 tools/analysis/agent_feature_parity_check.py --scan-default-candidates
```

### Candidate file scan

```bash
py -3 tools/analysis/agent_feature_parity_check.py --candidate-file docs/reports/tableau_candidates.txt
```

### Strict upstream mode

```bash
py -3 tools/analysis/agent_feature_parity_check.py --upstream-repo OWNER/REPO --strict-upstream
```

### JSON output (for CI integration)

```bash
py -3 tools/analysis/agent_feature_parity_check.py --upstream-repo OWNER/REPO --json
```

## How upstream comparison works

For each required local agent file, the script attempts to fetch:
- https://raw.githubusercontent.com/OWNER/REPO/BRANCH/.github/agents/<name>

It then reports:
- present_upstream
- missing_upstream
- hash_equal
- hash_different

For feature parity, it checks upstream presence of required modules and required flags in upstream `migrate.py`.

## Recommended Next Step

1. Confirm the canonical TableauToPowerBI upstream repository (owner/repo).
2. Run the upstream parity command and archive JSON output in this docs/reports folder.
3. Add a CI job for upstream parity if and only if upstream endpoint is stable and public.

