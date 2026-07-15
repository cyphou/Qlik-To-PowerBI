"""Tests for simplified migration presets in migrate.py."""

from argparse import Namespace

from migrate import _apply_simple_mode_preset


def _base_args(simple_mode: str):
    return Namespace(
        simple_mode=simple_mode,
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
