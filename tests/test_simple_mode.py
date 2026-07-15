"""Tests for compact preset and argument alias behavior in migrate.py."""

from argparse import Namespace

from migrate import _apply_argument_simplification, _apply_preset_profile


def _base_args(preset: str):
    return Namespace(
        preset=preset,
        source=None,
        src=None,
        out=None,
        workspace=None,
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


def test_preset_fast_applies_expected_values():
    args = _base_args("fast")
    out = _apply_preset_profile(args)
    assert out.ensure_open is True
    assert out.ensure_open_strict is False
    assert out.rewrite_policy == "conservative"
    assert out.autoheal_iterations == 1
    assert out.verify_open is False
    assert out.validate is False


def test_preset_balanced_applies_expected_values():
    args = _base_args("balanced")
    out = _apply_preset_profile(args)
    assert out.ensure_open is True
    assert out.ensure_open_strict is False
    assert out.rewrite_policy == "balanced"
    assert out.autoheal_iterations == 3
    assert out.verify_open is True
    assert out.validate is True


def test_preset_max_applies_expected_values():
    args = _base_args("max")
    out = _apply_preset_profile(args)
    assert out.ensure_open is True
    assert out.ensure_open_strict is True
    assert out.rewrite_policy == "aggressive"
    assert out.autoheal_iterations == 5
    assert out.autoheal is True
    assert out.qa is True
    assert out.compare is True
    assert out.gate == "prod"


def test_preset_unknown_keeps_values():
    args = _base_args("unknown")
    out = _apply_preset_profile(args)
    assert out.ensure_open is False
    assert out.rewrite_policy == "balanced"
    assert out.autoheal_iterations == 3


def test_source_file_maps_to_qlik_file():
    args = _base_args("balanced")
    args.source = "app.qvf"
    out = _apply_argument_simplification(args)
    assert out.qlik_file == "app.qvf"


def test_source_folder_maps_to_batch():
    args = _base_args("balanced")
    args.source = "exports/"
    out = _apply_argument_simplification(args)
    assert out.batch == "exports/"


def test_workspace_maps_to_deploy():
    args = _base_args("balanced")
    args.workspace = "ws-123"
    out = _apply_argument_simplification(args)
    assert out.deploy == "ws-123"


def test_src_alias_maps_to_qlik_file():
    args = _base_args("balanced")
    args.src = "app.qvf"
    out = _apply_argument_simplification(args)
    assert out.qlik_file == "app.qvf"


def test_out_alias_maps_to_output_dir():
    args = _base_args("balanced")
    args.out = "output/custom"
    out = _apply_argument_simplification(args)
    assert out.output_dir == "output/custom"
