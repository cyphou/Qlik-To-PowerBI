from powerbi_import.quality_gates import QualityGate, GateEnvironment


def test_dev_allows_high_severity_noncritical_failures():
    gate = QualityGate()
    metrics = {
        "fidelity_score": 60,
        "error_count": 0,
        "pii_fields_detected": 0,
        "pii_fields_masked": 0,
        "measure_count": 5,
    }

    result = gate.evaluate("dev-app", GateEnvironment.DEV, metrics)

    assert result.overall_passed is True
    assert result.blocked_reasons == []


def test_test_blocks_high_severity_failures():
    gate = QualityGate()
    metrics = {
        "fidelity_score": 60,
        "error_count": 0,
        "rls_audit_passed": False,
        "pii_fields_detected": 0,
        "pii_fields_masked": 0,
        "measure_count": 5,
    }

    result = gate.evaluate("test-app", GateEnvironment.TEST, metrics)

    assert result.overall_passed is False
    assert any("Fidelity score 60% below threshold of 85%" in reason for reason in result.blocked_reasons)
    assert any("RLS audit required before prod deployment" in reason for reason in result.blocked_reasons)
    assert result.approval_required is False


def test_test_fast_profile_does_not_require_rls_audit():
    gate = QualityGate()
    metrics = {
        "fidelity_score": 100,
        "error_count": 0,
        "migration_profile": "fast",
        "rls_audit_passed": False,
        "pii_fields_detected": 0,
        "pii_fields_masked": 0,
        "measure_count": 5,
    }

    result = gate.evaluate("fast-test-app", GateEnvironment.TEST, metrics)

    assert result.overall_passed is True
    assert all("RLS audit required before prod deployment" not in reason for reason in result.blocked_reasons)


def test_test_strict_profile_requires_rls_audit():
    gate = QualityGate()
    metrics = {
        "fidelity_score": 100,
        "error_count": 0,
        "migration_profile": "strict",
        "rls_audit_passed": False,
        "pii_fields_detected": 0,
        "pii_fields_masked": 0,
        "measure_count": 5,
    }

    result = gate.evaluate("strict-test-app", GateEnvironment.TEST, metrics)

    assert result.overall_passed is False
    assert any("RLS audit required before prod deployment" in reason for reason in result.blocked_reasons)


def test_prod_blocks_high_failures_and_requires_approval():
    gate = QualityGate()
    metrics = {
        "fidelity_score": 88,
        "error_count": 0,
        "rls_audit_passed": False,
        "pii_fields_detected": 0,
        "pii_fields_masked": 0,
        "image_count": 1,
        "images_reviewed": False,
        "m_query_count": 2,
        "m_queries_reviewed": False,
        "measure_count": 10,
    }

    result = gate.evaluate("prod-app", GateEnvironment.PROD, metrics)

    assert result.overall_passed is False
    assert result.approval_required is True
    assert any("Fidelity score 88% below threshold of 90%" in reason for reason in result.blocked_reasons)
    assert any("RLS audit required before prod deployment" in reason for reason in result.blocked_reasons)
