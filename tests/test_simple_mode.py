"""Tests for simplified migration presets in migrate.py."""

from argparse import Namespace

from migrate import _apply_simple_command, _apply_simple_mode_preset


def _base_args(simple_mode: str):
    return Namespace(
        simple_mode=simple_mode,
        simple_command=None,
        target=None,
        workspace_id=None,
        qlik_file=None,
        batch=None,
        batch_recursive=False,
        deploy=None,
        server_test=False,
        ensure_open=False,
        ensure_open_strict=False,
        rewrite_policy="balanced",
        autoheal_iterations=3,
        verify_open=False,
        autoheal=False,
        validate=False,
        post_check=False,
        qa=False,
        compare=False,
        gate=None,
        output_format="pbip",
    )


def test_simple_mode_fast_applies_expected_values():
    args = _base_args("fast")
    out = _apply_simple_mode_preset(args)
    assert out.ensure_open is True
    assert out.ensure_open_strict is False
    assert out.rewrite_policy == "conservative"
    assert out.autoheal_iterations == 1
    assert out.verify_open is False
    assert out.validate is False


def test_simple_mode_balanced_applies_expected_values():
    args = _base_args("balanced")
    out = _apply_simple_mode_preset(args)
    assert out.ensure_open is True
    assert out.ensure_open_strict is False
    assert out.rewrite_policy == "balanced"
    assert out.autoheal_iterations == 3
    assert out.verify_open is True
    assert out.validate is True


def test_simple_mode_max_applies_expected_values():
    args = _base_args("max")
    out = _apply_simple_mode_preset(args)
    assert out.ensure_open is True
    assert out.ensure_open_strict is True
    assert out.rewrite_policy == "aggressive"
    assert out.autoheal_iterations == 5
    assert out.autoheal is True
    assert out.qa is True
    assert out.compare is True
    assert out.gate == "prod"


def test_simple_mode_unknown_keeps_values():
    args = _base_args("unknown")
    out = _apply_simple_mode_preset(args)
    assert out.ensure_open is False
    assert out.rewrite_policy == "balanced"
    assert out.autoheal_iterations == 3


def test_simple_command_migrate_maps_target_to_qlik_file():
    args = _base_args("balanced")
    args.simple_command = "migrate"
    args.target = "app.qvf"
    out = _apply_simple_command(args)
    assert out.qlik_file == "app.qvf"
    assert out.simple_mode == "balanced"


def test_simple_command_batch_maps_target_to_batch():
    args = _base_args("balanced")
    args.simple_command = "batch"
    args.target = "exports"
    out = _apply_simple_command(args)
    assert out.batch == "exports"
    assert out.batch_recursive is True


def test_simple_command_deploy_maps_workspace_and_target():
    args = _base_args("balanced")
    args.simple_command = "deploy"
    args.target = "app.qvf"
    args.workspace_id = "ws-123"
    out = _apply_simple_command(args)
    assert out.qlik_file == "app.qvf"
    assert out.deploy == "ws-123"


def test_simple_command_server_test_enables_server_test():
    args = _base_args("balanced")
    args.simple_command = "server-test"
    out = _apply_simple_command(args)
    assert out.server_test is True
