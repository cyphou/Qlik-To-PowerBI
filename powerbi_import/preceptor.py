"""Preceptorship loop engine for migration artifact quality review.

Implements the DRAFT → REVIEW → APPROVE/COACH cycle that validates
generated Power BI artifacts against the source Qlik extraction,
scoring 6 quality dimensions and providing structured coaching
feedback when artifacts fall below the 4-star threshold.

Usage:
    from powerbi_import.preceptor import PreceptorLoop

    loop = PreceptorLoop()
    result = loop.run(
        pbip_path="artifacts/powerbi_projects/MyReport",
        extraction_dir="qlik_export",
        max_cycles=3,
        on_escalate="warn",
    )
    result.to_console()
    result.to_json("artifacts/review_report.json")
"""

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path

logger = logging.getLogger('qlik_to_powerbi.preceptor')

# ── Constants ────────────────────────────────────────────────────

DIMENSIONS = (
    'completeness',
    'dax_correctness',
    'm_query_validity',
    'tmdl_structure',
    'pbir_fidelity',
    'visual_equivalence',
)

MIN_PASS_SCORE = 4.0
MAX_CYCLES = 3
SSIM_THRESHOLD = 0.85

# Qlik functions that must NOT appear in DAX output
_QLIK_LEAK_RE = [
    re.compile(r'\bAGGR\s*\(', re.IGNORECASE),
    re.compile(r'\bALT\s*\(', re.IGNORECASE),
    re.compile(r'\bONLY\s*\(', re.IGNORECASE),
    re.compile(r'\bPEEK\s*\(', re.IGNORECASE),
    re.compile(r'\bPREVIOUS\s*\(', re.IGNORECASE),
    re.compile(r'\bABOVE\s*\(', re.IGNORECASE),
    re.compile(r'\bBELOW\s*\(', re.IGNORECASE),
    re.compile(r'\bFieldValue\s*\(', re.IGNORECASE),
    re.compile(r'\bGetFieldSelections\s*\(', re.IGNORECASE),
    re.compile(r'\bGetSelectedCount\s*\(', re.IGNORECASE),
    re.compile(r'\bMatch\s*\(', re.IGNORECASE),
    re.compile(r'\bWildMatch\s*\(', re.IGNORECASE),
    re.compile(r'\bPick\s*\(', re.IGNORECASE),
    re.compile(r'\bClass\s*\(', re.IGNORECASE),
    re.compile(r'\bDual\s*\(', re.IGNORECASE),
    re.compile(r'\bApplyMap\s*\(', re.IGNORECASE),
    re.compile(r'\bRangeSum\s*\(', re.IGNORECASE),
    re.compile(r'\bRangeAvg\s*\(', re.IGNORECASE),
    re.compile(r'\bRangeCount\s*\(', re.IGNORECASE),
]

_M_IF_RE = re.compile(r'\bif\b', re.IGNORECASE)
_M_THEN_RE = re.compile(r'\bthen\b', re.IGNORECASE)
_M_ELSE_RE = re.compile(r'\belse\b', re.IGNORECASE)
_OPEN_PAREN_RE = re.compile(r'\(')
_CLOSE_PAREN_RE = re.compile(r'\)')


# ── Data classes ─────────────────────────────────────────────────

class CoachingItem:
    """A single coaching feedback item."""

    def __init__(self, dimension, score, issue, location='', fix='',
                 example_before='', example_after=''):
        self.dimension = dimension
        self.score = score
        self.issue = issue
        self.location = location
        self.fix = fix
        self.example_before = example_before
        self.example_after = example_after

    def to_dict(self):
        d = {
            'dimension': self.dimension,
            'score': self.score,
            'issue': self.issue,
        }
        if self.location:
            d['location'] = self.location
        if self.fix:
            d['fix'] = self.fix
        if self.example_before:
            d['example_before'] = self.example_before
        if self.example_after:
            d['example_after'] = self.example_after
        return d


class ReviewScorecard:
    """Scores across the 6 review dimensions."""

    def __init__(self):
        self.scores = {}
        self.details = {}

    def set_score(self, dimension, score, detail=''):
        self.scores[dimension] = max(1, min(5, score))
        if detail:
            self.details[dimension] = detail

    def average(self):
        if not self.scores:
            return 0.0
        return sum(self.scores.values()) / len(self.scores)

    def passed(self):
        return self.average() >= MIN_PASS_SCORE

    def to_dict(self):
        return {
            'scores': dict(self.scores),
            'details': dict(self.details),
            'average': round(self.average(), 2),
            'passed': self.passed(),
        }


class ReviewCycle:
    """One cycle of the preceptorship loop."""

    def __init__(self, cycle_number):
        self.cycle_number = cycle_number
        self.scorecard = ReviewScorecard()
        self.coaching_items = []
        self.timestamp = datetime.now().isoformat()

    def add_coaching(self, item):
        self.coaching_items.append(item)

    def to_dict(self):
        return {
            'cycle': self.cycle_number,
            'timestamp': self.timestamp,
            'scorecard': self.scorecard.to_dict(),
            'coaching_items': [c.to_dict() for c in self.coaching_items],
        }


class ReviewReport:
    """Full report across all review cycles."""

    APPROVED = 'approved'
    COACHING = 'coaching'
    ESCALATED_WARN = 'escalated_warn'
    ESCALATED_BLOCK = 'escalated_block'

    def __init__(self, report_name):
        self.report_name = report_name
        self.created_at = datetime.now().isoformat()
        self.cycles = []
        self.status = self.COACHING
        self.escalation_reason = ''

    @property
    def final_scorecard(self):
        if self.cycles:
            return self.cycles[-1].scorecard
        return ReviewScorecard()

    @property
    def total_cycles(self):
        return len(self.cycles)

    def add_cycle(self, cycle):
        self.cycles.append(cycle)

    def to_dict(self):
        return {
            'report_name': self.report_name,
            'created_at': self.created_at,
            'status': self.status,
            'total_cycles': self.total_cycles,
            'final_score': round(self.final_scorecard.average(), 2),
            'final_passed': self.final_scorecard.passed(),
            'escalation_reason': self.escalation_reason,
            'cycles': [c.to_dict() for c in self.cycles],
        }

    def to_json(self, output_path):
        output_path = str(output_path)
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.info("Review report saved to %s", output_path)

    def to_console(self):
        sc = self.final_scorecard
        status_icon = {
            self.APPROVED: '[OK]',
            self.COACHING: '[..]',
            self.ESCALATED_WARN: '[!!]',
            self.ESCALATED_BLOCK: '[XX]',
        }.get(self.status, '?')

        print(f"\n{'=' * 60}")
        print(f"  PRECEPTORSHIP REVIEW -- {self.report_name}")
        print(f"{'=' * 60}")
        print(f"  Status: {status_icon} {self.status.upper()}")
        print(f"  Cycles: {self.total_cycles}")
        print(f"  Final Score: {sc.average():.1f}/5.0")
        print()

        for dim in DIMENSIONS:
            score = sc.scores.get(dim, 0)
            label = dim.replace('_', ' ').title()
            bar = '*' * score + '.' * (5 - score)
            detail = sc.details.get(dim, '')
            suffix = f" -- {detail}" if detail else ''
            print(f"  {label:20s} {bar}{suffix}")

        if self.cycles:
            last = self.cycles[-1]
            if last.coaching_items:
                print(f"\n  COACH FEEDBACK -- Cycle {last.cycle_number}/{MAX_CYCLES}")
                print(f"  {'-' * 50}")
                for item in last.coaching_items:
                    label = item.dimension.replace('_', ' ').title()
                    print(f"  Dimension: {label} -- {item.score}*")
                    print(f"  Issue: {item.issue}")
                    if item.location:
                        print(f"  Location: {item.location}")
                    if item.fix:
                        print(f"  Fix: {item.fix}")
                    print()

        if self.escalation_reason:
            print(f"  Escalation: {self.escalation_reason}")
        print(f"{'=' * 60}\n")


# ── Dimension Reviewers ──────────────────────────────────────────

def _load_json_safe(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def _count_tmdl_objects(sm_dir):
    counts = {'tables': 0, 'measures': 0, 'columns': 0, 'relationships': 0}
    sm_path = Path(sm_dir)
    tables_dir = sm_path / 'definition' / 'tables'
    if tables_dir.exists():
        counts['tables'] = len(list(tables_dir.glob('*.tmdl')))
    for tmdl_file in (tables_dir.glob('*.tmdl') if tables_dir.exists() else []):
        try:
            content = tmdl_file.read_text(encoding='utf-8')
            counts['measures'] += len(re.findall(r'^\s*measure\s+', content, re.MULTILINE))
            counts['columns'] += len(re.findall(r'^\s*column\s+', content, re.MULTILINE))
        except OSError:
            pass
    rel_file = sm_path / 'definition' / 'relationships.tmdl'
    if rel_file.exists():
        try:
            content = rel_file.read_text(encoding='utf-8')
            counts['relationships'] = len(re.findall(r'^\s*relationship\s+', content, re.MULTILINE))
        except OSError:
            pass
    return counts


def _review_completeness(pbip_path, extraction_data):
    coaching = []
    issues = []
    pbip = Path(pbip_path)
    report_name = pbip.name

    src_sheets = len(extraction_data.get('sheets', []))
    src_measures = len(extraction_data.get('measures', []))
    src_datasources = len(extraction_data.get('datasources', []))
    src_dimensions = len(extraction_data.get('dimensions', []))
    src_variables = len(extraction_data.get('variables', []))

    sm_dir = pbip / f'{report_name}.SemanticModel'
    tmdl_counts = _count_tmdl_objects(str(sm_dir))

    report_dir = pbip / f'{report_name}.Report' / 'definition' / 'pages'
    out_visuals = 0
    if report_dir.exists():
        for page_dir in report_dir.iterdir():
            if page_dir.is_dir():
                visuals_dir = page_dir / 'visuals'
                if visuals_dir.exists():
                    out_visuals += len(list(visuals_dir.glob('*/visual.json')))

    penalties = 0

    if src_sheets > 0 and out_visuals == 0:
        issues.append(f"No visuals generated for {src_sheets} source sheets")
        penalties += 2
    elif src_sheets > 0 and out_visuals < src_sheets:
        missing = src_sheets - out_visuals
        issues.append(f"{missing}/{src_sheets} sheets missing visuals")
        penalties += 1

    out_measures_cols = tmdl_counts['measures'] + tmdl_counts['columns']
    if src_measures > 0 and out_measures_cols == 0:
        issues.append(f"No measures/columns for {src_measures} master measures")
        penalties += 2
    elif src_measures > 5 and out_measures_cols < src_measures * 0.5:
        issues.append(f"Only {out_measures_cols} measures/columns for {src_measures} master measures")
        penalties += 1

    if src_datasources > 0 and tmdl_counts['tables'] == 0:
        issues.append(f"No tables generated for {src_datasources} datasources")
        penalties += 2

    score = max(1, 5 - penalties)
    detail = f"{out_visuals} visuals, {tmdl_counts['tables']} tables, {out_measures_cols} measures/cols"

    for issue in issues:
        coaching.append(CoachingItem(
            dimension='completeness', score=score, issue=issue,
            fix='Ensure all source objects are mapped in the generation pipeline',
        ))

    return score, detail, coaching


def _review_dax_correctness(pbip_path, extraction_data):
    coaching = []
    pbip = Path(pbip_path)
    report_name = pbip.name
    sm_dir = pbip / f'{report_name}.SemanticModel' / 'definition' / 'tables'

    leak_count = 0
    paren_errors = 0
    total_formulas = 0

    if sm_dir.exists():
        for tmdl_file in sm_dir.glob('*.tmdl'):
            try:
                content = tmdl_file.read_text(encoding='utf-8')
            except OSError:
                continue
            expressions = re.findall(
                r'(?:expression\s*=\s*|=\s+)(.*?)(?:\n\s*(?:formatString|description|displayFolder|dataType|lineageTag|annotation|isHidden|summarizeBy|dataCategory|sortByColumn)\s*=|\Z)',
                content, re.DOTALL,
            )
            for expr in expressions:
                expr = expr.strip()
                if not expr or expr.startswith('```') or expr.startswith('let'):
                    continue
                total_formulas += 1
                for pat in _QLIK_LEAK_RE:
                    match = pat.search(expr)
                    if match:
                        leak_count += 1
                        coaching.append(CoachingItem(
                            dimension='dax_correctness', score=0,
                            issue=f"Qlik function leaked into DAX: {match.group().strip()}",
                            location=str(tmdl_file),
                            fix=f"Convert {match.group().strip()} to its DAX equivalent",
                            example_before=match.group().strip(),
                        ))
                        break
                opens = len(_OPEN_PAREN_RE.findall(expr))
                closes = len(_CLOSE_PAREN_RE.findall(expr))
                if opens != closes:
                    paren_errors += 1
                    coaching.append(CoachingItem(
                        dimension='dax_correctness', score=0,
                        issue=f"Unbalanced parentheses: {opens} open vs {closes} close",
                        location=str(tmdl_file),
                        fix="Fix parenthesis balance in the DAX expression",
                    ))

    penalties = 0
    if leak_count > 0:
        penalties += min(3, leak_count)
    if paren_errors > 0:
        penalties += min(2, paren_errors)

    score = max(1, 5 - penalties)
    detail = f"{total_formulas} formulas, {leak_count} leaks, {paren_errors} paren errors"
    for item in coaching:
        item.score = score
    return score, detail, coaching


def _review_m_query_validity(pbip_path, extraction_data):
    coaching = []
    pbip = Path(pbip_path)
    report_name = pbip.name
    sm_dir = pbip / f'{report_name}.SemanticModel' / 'definition' / 'tables'

    if_else_errors = 0
    total_m_exprs = 0
    single_quote_errors = 0

    if sm_dir.exists():
        for tmdl_file in sm_dir.glob('*.tmdl'):
            try:
                content = tmdl_file.read_text(encoding='utf-8')
            except OSError:
                continue
            m_blocks = re.findall(r'```\s*(.*?)```', content, re.DOTALL)
            for block in m_blocks:
                block = block.strip()
                if not block:
                    continue
                total_m_exprs += 1
                ifs = len(_M_IF_RE.findall(block))
                elses = len(_M_ELSE_RE.findall(block))
                if ifs > 0 and ifs != elses:
                    if_else_errors += 1
                    coaching.append(CoachingItem(
                        dimension='m_query_validity', score=0,
                        issue=f"Unbalanced M if/else: {ifs} if vs {elses} else",
                        location=str(tmdl_file),
                        fix="Add missing 'else null' clause to every 'if' expression",
                    ))
                single_quotes_in_set = re.findall(r"\{[^}]*'[^']*'[^}]*\}", block)
                if single_quotes_in_set:
                    single_quote_errors += 1
                    coaching.append(CoachingItem(
                        dimension='m_query_validity', score=0,
                        issue="Single-quoted strings in M set literal (should be double-quoted)",
                        location=str(tmdl_file),
                        fix="Replace single quotes with double quotes in M set literals",
                        example_before="{'value1', 'value2'}",
                        example_after='{"value1", "value2"}',
                    ))

    penalties = 0
    if if_else_errors > 0:
        penalties += min(3, if_else_errors)
    if single_quote_errors > 0:
        penalties += min(2, single_quote_errors)

    score = max(1, 5 - penalties)
    detail = f"{total_m_exprs} M expressions, {if_else_errors} if/else errors, {single_quote_errors} quote errors"
    for item in coaching:
        item.score = score
    return score, detail, coaching


def _review_tmdl_structure(pbip_path, extraction_data):
    coaching = []
    pbip = Path(pbip_path)
    report_name = pbip.name
    sm_dir = pbip / f'{report_name}.SemanticModel'
    def_dir = sm_dir / 'definition'

    penalties = 0

    model_file = def_dir / 'model.tmdl'
    if not model_file.exists():
        penalties += 3
        coaching.append(CoachingItem(
            dimension='tmdl_structure', score=0,
            issue="model.tmdl not found", location=str(def_dir),
            fix="Ensure TMDLGenerator produces model.tmdl",
        ))
    else:
        try:
            model_content = model_file.read_text(encoding='utf-8')
        except OSError:
            model_content = ''

        src_associations = extraction_data.get('associations', [])
        if src_associations:
            rel_file = def_dir / 'relationships.tmdl'
            if not rel_file.exists():
                if 'ref relationship' not in model_content and 'relationship ' not in model_content:
                    penalties += 1
                    coaching.append(CoachingItem(
                        dimension='tmdl_structure', score=0,
                        issue=f"{len(src_associations)} source associations but none in TMDL",
                        fix="Check relationship extraction and TMDL generation",
                    ))

        has_date_cols = False
        for ds in extraction_data.get('datasources', []):
            if isinstance(ds, dict):
                for table in ds.get('tables', []):
                    for col in table.get('columns', []):
                        if col.get('datatype', '').lower() in ('date', 'datetime', 'timestamp'):
                            has_date_cols = True
                            break
        if has_date_cols:
            calendar_exists = (def_dir / 'tables' / 'Calendar.tmdl').exists()
            if not calendar_exists and 'Calendar' not in model_content:
                penalties += 1
                coaching.append(CoachingItem(
                    dimension='tmdl_structure', score=0,
                    issue="Date columns found but no Calendar table generated",
                    fix="Ensure auto-Calendar generation is enabled for date columns",
                ))

    score = max(1, 5 - penalties)
    tmdl_counts = _count_tmdl_objects(str(sm_dir))
    detail = (f"{tmdl_counts['tables']} tables, {tmdl_counts['relationships']} rels, "
              f"{tmdl_counts['measures']} measures")
    for item in coaching:
        item.score = score
    return score, detail, coaching


def _review_pbir_fidelity(pbip_path, extraction_data):
    coaching = []
    pbip = Path(pbip_path)
    report_name = pbip.name
    report_dir = pbip / f'{report_name}.Report'
    def_dir = report_dir / 'definition'

    penalties = 0

    report_json = def_dir / 'report.json'
    if not report_json.exists():
        penalties += 3
        coaching.append(CoachingItem(
            dimension='pbir_fidelity', score=0,
            issue="report.json not found", location=str(def_dir),
            fix="Ensure PBIPGenerator produces report.json",
        ))
        score = max(1, 5 - penalties)
        for item in coaching:
            item.score = score
        return score, "report.json missing", coaching

    src_sheets = extraction_data.get('sheets', [])
    pages_dir = def_dir / 'pages'
    out_pages = 0
    if pages_dir.exists():
        out_pages = len([d for d in pages_dir.iterdir() if d.is_dir()])

    if src_sheets and out_pages == 0:
        penalties += 2
        coaching.append(CoachingItem(
            dimension='pbir_fidelity', score=0,
            issue=f"{len(src_sheets)} sheets but no report pages generated",
            fix="Check page generation in PBIPGenerator",
        ))

    invalid_visuals = 0
    total_visuals = 0
    if pages_dir.exists():
        for page_dir in pages_dir.iterdir():
            if not page_dir.is_dir():
                continue
            visuals_dir = page_dir / 'visuals'
            if not visuals_dir.exists():
                continue
            for visual_dir in visuals_dir.iterdir():
                if not visual_dir.is_dir():
                    continue
                visual_json = visual_dir / 'visual.json'
                if visual_json.exists():
                    total_visuals += 1
                    try:
                        with open(visual_json, 'r', encoding='utf-8') as f:
                            vdata = json.load(f)
                        if not isinstance(vdata, dict):
                            invalid_visuals += 1
                        elif '$schema' not in vdata:
                            invalid_visuals += 1
                    except (json.JSONDecodeError, OSError):
                        invalid_visuals += 1

    if invalid_visuals > 0:
        penalties += min(2, invalid_visuals)
        coaching.append(CoachingItem(
            dimension='pbir_fidelity', score=0,
            issue=f"{invalid_visuals}/{total_visuals} visual JSON files are invalid",
            fix="Check visual JSON generation in visual_generator.py",
        ))

    pbir_file = def_dir / 'definition.pbir'
    if not pbir_file.exists():
        penalties += 1
        coaching.append(CoachingItem(
            dimension='pbir_fidelity', score=0,
            issue="definition.pbir not found", location=str(def_dir),
            fix="Ensure PBIPGenerator produces definition.pbir",
        ))

    score = max(1, 5 - penalties)
    detail = f"{out_pages} pages, {total_visuals} visuals, {invalid_visuals} invalid"
    for item in coaching:
        item.score = score
    return score, detail, coaching


def _review_visual_equivalence(pbip_path, extraction_data, screenshots_dir=None):
    coaching = []
    pbip = Path(pbip_path)

    if screenshots_dir is None:
        candidates = [pbip / 'screenshots', pbip.parent / 'screenshots']
        if isinstance(extraction_data, dict) and extraction_data.get('_extraction_dir'):
            candidates.append(Path(extraction_data['_extraction_dir']) / 'screenshots')
        screenshots_dir = next((c for c in candidates if c.exists()), None)
    else:
        screenshots_dir = Path(screenshots_dir)
        if not screenshots_dir.exists():
            screenshots_dir = None

    if screenshots_dir is None:
        return 5, 'no screenshots provided (skipped)', []

    source_dir = screenshots_dir / 'source'
    output_dir = screenshots_dir / 'output'

    if not source_dir.exists() or not output_dir.exists():
        return 5, 'screenshots dir missing source/ or output/ (skipped)', []

    source_files = {}
    for ext in ('*.png', '*.jpg', '*.jpeg'):
        for f in source_dir.glob(ext):
            source_files[f.stem.lower()] = f

    if not source_files:
        return 5, 'no source screenshots found (skipped)', []

    total_pairs = 0
    passed_pairs = 0
    failed_pairs = []
    ssim_scores = []

    for name, src_path in source_files.items():
        out_path = None
        for ext in ('*.png', '*.jpg', '*.jpeg'):
            for m in output_dir.glob(ext):
                if m.stem.lower() == name:
                    out_path = m
                    break
            if out_path:
                break

        if not out_path:
            failed_pairs.append(name)
            coaching.append(CoachingItem(
                dimension='visual_equivalence', score=0,
                issue=f"No output screenshot found for '{name}'",
                location=str(src_path),
                fix=f"Capture Power BI screenshot for '{name}' and save to {output_dir}",
            ))
            continue

        total_pairs += 1
        try:
            src_data = src_path.read_bytes()
            out_data = out_path.read_bytes()
        except OSError as e:
            failed_pairs.append(name)
            coaching.append(CoachingItem(
                dimension='visual_equivalence', score=0,
                issue=f"Cannot read screenshot files for '{name}': {e}",
                location=str(src_path),
            ))
            continue

        try:
            from powerbi_import.equivalence_tester import compute_ssim
        except ImportError:
            try:
                from equivalence_tester import compute_ssim
            except ImportError:
                return 5, 'SSIM not available (skipped)', []

        ssim = compute_ssim(src_data, out_data)
        ssim_scores.append(ssim)

        if ssim >= SSIM_THRESHOLD:
            passed_pairs += 1
        else:
            failed_pairs.append(name)
            coaching.append(CoachingItem(
                dimension='visual_equivalence', score=0,
                issue=f"Visual '{name}' SSIM={ssim:.3f} below threshold {SSIM_THRESHOLD}",
                location=f"source: {src_path}, output: {out_path}",
                fix=f"Review visual '{name}' -- layout, colors, or data may differ",
            ))

    if total_pairs == 0 and failed_pairs:
        score = max(1, 5 - len(failed_pairs))
    elif total_pairs == 0:
        score = 5
    else:
        avg_ssim = sum(ssim_scores) / len(ssim_scores) if ssim_scores else 0.0
        pass_rate = passed_pairs / total_pairs
        if avg_ssim >= 0.95 and pass_rate == 1.0:
            score = 5
        elif avg_ssim >= SSIM_THRESHOLD and pass_rate >= 0.8:
            score = 4
        elif avg_ssim >= 0.70 and pass_rate >= 0.5:
            score = 3
        elif avg_ssim >= 0.50:
            score = 2
        else:
            score = 1
        if failed_pairs:
            score = max(1, score - 1)

    avg_display = f"{sum(ssim_scores)/len(ssim_scores):.3f}" if ssim_scores else 'N/A'
    detail = (f"{passed_pairs}/{total_pairs} pairs pass SSIM>={SSIM_THRESHOLD}, "
              f"avg={avg_display}, {len(failed_pairs)} issues")
    for item in coaching:
        item.score = score
    return score, detail, coaching


_DIMENSION_REVIEWERS = {
    'completeness': _review_completeness,
    'dax_correctness': _review_dax_correctness,
    'm_query_validity': _review_m_query_validity,
    'tmdl_structure': _review_tmdl_structure,
    'pbir_fidelity': _review_pbir_fidelity,
    'visual_equivalence': _review_visual_equivalence,
}


def _load_extraction_data(extraction_dir):
    """Load the 11 Qlik extraction JSON files into a unified dict."""
    extraction_dir = Path(extraction_dir)
    data = {}
    json_files = [
        'app_metadata', 'datasources', 'dimensions', 'measures',
        'visualizations', 'sheets', 'variables', 'loadscript',
        'associations', 'bookmarks', 'master_items',
    ]
    for name in json_files:
        path = extraction_dir / f'{name}.json'
        if path.exists():
            loaded = _load_json_safe(str(path))
            data[name] = loaded if isinstance(loaded, list) else loaded.get(name, loaded)
        else:
            data[name] = []
    return data


# ── Main Loop ────────────────────────────────────────────────────

class PreceptorLoop:
    """The preceptorship quality loop engine."""

    def __init__(self, min_score=MIN_PASS_SCORE, max_cycles=MAX_CYCLES):
        self.min_score = min_score
        self.max_cycles = max_cycles

    def review(self, pbip_path, extraction_data, screenshots_dir=None):
        cycle = ReviewCycle(cycle_number=1)
        for dimension in DIMENSIONS:
            reviewer_fn = _DIMENSION_REVIEWERS[dimension]
            if dimension == 'visual_equivalence':
                score, detail, coaching_items = reviewer_fn(
                    pbip_path, extraction_data, screenshots_dir)
            else:
                score, detail, coaching_items = reviewer_fn(
                    pbip_path, extraction_data)
            cycle.scorecard.set_score(dimension, score, detail)
            for item in coaching_items:
                cycle.add_coaching(item)
        return cycle

    def run(self, pbip_path, extraction_dir, max_cycles=None,
            on_escalate='warn', screenshots_dir=None):
        pbip_path = str(pbip_path)
        max_cycles = max_cycles or self.max_cycles
        report_name = Path(pbip_path).name
        report = ReviewReport(report_name)

        if isinstance(extraction_dir, dict):
            extraction_data = extraction_dir
        else:
            extraction_data = _load_extraction_data(extraction_dir)

        for cycle_num in range(1, max_cycles + 1):
            logger.info("Preceptorship review cycle %d/%d for %s",
                        cycle_num, max_cycles, report_name)
            cycle = ReviewCycle(cycle_number=cycle_num)
            for dimension in DIMENSIONS:
                reviewer_fn = _DIMENSION_REVIEWERS[dimension]
                if dimension == 'visual_equivalence':
                    score, detail, coaching_items = reviewer_fn(
                        pbip_path, extraction_data, screenshots_dir)
                else:
                    score, detail, coaching_items = reviewer_fn(
                        pbip_path, extraction_data)
                cycle.scorecard.set_score(dimension, score, detail)
                for item in coaching_items:
                    cycle.add_coaching(item)
            report.add_cycle(cycle)

            if cycle.scorecard.passed():
                report.status = ReviewReport.APPROVED
                logger.info("Review APPROVED at cycle %d (score %.1f)",
                            cycle_num, cycle.scorecard.average())
                return report

            logger.info("Review cycle %d: score %.1f < %.1f",
                        cycle_num, cycle.scorecard.average(), self.min_score)

        if on_escalate == 'block':
            report.status = ReviewReport.ESCALATED_BLOCK
            report.escalation_reason = (
                f"Failed to reach {self.min_score} after {max_cycles} cycles. "
                f"Final score: {report.final_scorecard.average():.1f}. "
                f"Manual intervention required."
            )
        else:
            report.status = ReviewReport.ESCALATED_WARN
            report.escalation_reason = (
                f"Failed to reach {self.min_score} after {max_cycles} cycles. "
                f"Final score: {report.final_scorecard.average():.1f}. "
                f"Proceeding with quality warnings."
            )

        logger.warning("Preceptorship ESCALATED for %s: %s",
                        report_name, report.escalation_reason)
        return report


def run_preceptor_review(pbip_path, extraction_dir, *,
                         max_cycles=MAX_CYCLES, on_escalate='warn',
                         output_path=None, quiet=False,
                         screenshots_dir=None):
    loop = PreceptorLoop(max_cycles=max_cycles)
    report = loop.run(pbip_path, extraction_dir,
                      max_cycles=max_cycles, on_escalate=on_escalate,
                      screenshots_dir=screenshots_dir)
    if not quiet:
        report.to_console()
    if output_path:
        report.to_json(output_path)
    return report
