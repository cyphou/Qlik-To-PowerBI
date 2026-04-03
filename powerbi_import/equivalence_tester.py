"""Query Equivalence Tester — Cross-platform validation framework.

Compares Qlik and Power BI output to verify that migrated reports
produce equivalent data within configurable tolerance thresholds.

Features:
- Measure value comparison (Qlik expected vs PBI actual)
- Visual screenshot comparison framework (SSIM-based)
- Per-measure pass/fail validation report
"""

import json
import math
import os


def compare_measure_values(expected, actual, tolerance=0.01):
    """Compare two sets of measure values within a tolerance threshold.

    Args:
        expected: Dict of measure_name → numeric value (from Qlik)
        actual: Dict of measure_name → numeric value (from PBI)
        tolerance: Relative tolerance for floating-point comparison (default 1%)

    Returns:
        dict with:
        - 'passed': total measures passing
        - 'failed': total measures failing
        - 'missing': measures in expected but not in actual
        - 'details': list of per-measure comparison dicts
    """
    details = []
    passed = 0
    failed = 0
    missing = []

    for name, exp_val in expected.items():
        if name not in actual:
            missing.append(name)
            details.append({
                'measure': name,
                'expected': exp_val,
                'actual': None,
                'status': 'missing',
                'diff': None,
            })
            continue

        act_val = actual[name]
        try:
            exp_num = float(exp_val) if exp_val is not None else 0.0
            act_num = float(act_val) if act_val is not None else 0.0
        except (ValueError, TypeError):
            # Non-numeric — exact string match
            if str(exp_val) == str(act_val):
                passed += 1
                details.append({
                    'measure': name,
                    'expected': exp_val,
                    'actual': act_val,
                    'status': 'pass',
                    'diff': 0,
                })
            else:
                failed += 1
                details.append({
                    'measure': name,
                    'expected': exp_val,
                    'actual': act_val,
                    'status': 'fail',
                    'diff': None,
                })
            continue

        # Numeric comparison with tolerance
        if exp_num == 0 and act_num == 0:
            diff = 0.0
        elif exp_num == 0:
            diff = abs(act_num)
        else:
            diff = abs((act_num - exp_num) / exp_num)

        if diff <= tolerance:
            passed += 1
            status = 'pass'
        else:
            failed += 1
            status = 'fail'

        details.append({
            'measure': name,
            'expected': exp_val,
            'actual': act_val,
            'status': status,
            'diff': round(diff, 6),
        })

    return {
        'passed': passed,
        'failed': failed,
        'missing': missing,
        'total': len(expected),
        'details': details,
    }


def compute_ssim(img_a_data, img_b_data):
    """Compute structural similarity index between two images.

    This is a simplified SSIM approximation for migration validation.
    For production use, consider using scikit-image's structural_similarity.

    Args:
        img_a_data: bytes of image A (PNG)
        img_b_data: bytes of image B (PNG)

    Returns:
        float: SSIM value between 0 and 1 (1 = identical)
    """
    if not img_a_data or not img_b_data:
        return 0.0

    # Exact match shortcut
    if img_a_data == img_b_data:
        return 1.0

    # Simplified byte-level similarity (production should use pixel-level)
    len_a = len(img_a_data)
    len_b = len(img_b_data)
    if len_a == 0 or len_b == 0:
        return 0.0

    # Size similarity factor
    size_ratio = min(len_a, len_b) / max(len_a, len_b)

    # Byte-level overlap (sample first N bytes for performance)
    sample_size = min(1024, len_a, len_b)
    matches = sum(1 for a, b in zip(img_a_data[:sample_size], img_b_data[:sample_size]) if a == b)
    byte_similarity = matches / sample_size

    # Weighted combination
    ssim = 0.4 * size_ratio + 0.6 * byte_similarity
    return round(min(1.0, ssim), 4)


def compare_screenshots(img_a_data, img_b_data, threshold=0.85):
    """Compare two screenshot images and return pass/fail result.

    Args:
        img_a_data: bytes of Qlik screenshot (PNG)
        img_b_data: bytes of PBI screenshot (PNG)
        threshold: Minimum SSIM score to pass (default 0.85)

    Returns:
        dict with 'ssim', 'passed', 'threshold'
    """
    ssim = compute_ssim(img_a_data, img_b_data)
    return {
        'ssim': ssim,
        'passed': ssim >= threshold,
        'threshold': threshold,
    }


def generate_validation_report(measure_results, screenshot_results=None,
                                output_path=None):
    """Generate a comprehensive validation report.

    Args:
        measure_results: Output from compare_measure_values()
        screenshot_results: Optional list of compare_screenshots() outputs
        output_path: Optional path to write JSON report

    Returns:
        dict: Full validation report
    """
    report = {
        'measures': measure_results,
        'screenshots': screenshot_results or [],
        'overall_pass': (
            measure_results['failed'] == 0 and
            len(measure_results['missing']) == 0
        ),
    }

    if screenshot_results:
        report['overall_pass'] = (
            report['overall_pass'] and
            all(s.get('passed', False) for s in screenshot_results)
        )

    if output_path:
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

    return report
