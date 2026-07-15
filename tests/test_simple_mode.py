"""Tests for the single-command argument routing in migrate.py."""

from argparse import Namespace

from migrate import _apply_argument_simplification


def _base_args():
    return Namespace(
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


def test_source_file_maps_to_qlik_file():
    args = _base_args()
    args.source = "app.qvf"
    out = _apply_argument_simplification(args)
    assert out.qlik_file == "app.qvf"


def test_source_folder_maps_to_batch():
    args = _base_args()
    args.source = "exports/"
    out = _apply_argument_simplification(args)
    assert out.batch == "exports/"


def test_positional_folder_maps_to_batch():
    args = _base_args()
    args.qlik_file = "exports/"
    out = _apply_argument_simplification(args)
    assert out.batch == "exports/"
    assert out.qlik_file is None


def test_workspace_maps_to_deploy():
    args = _base_args()
    args.workspace = "ws-123"
    out = _apply_argument_simplification(args)
    assert out.deploy == "ws-123"


def test_src_alias_maps_to_qlik_file():
    args = _base_args()
    args.src = "app.qvf"
    out = _apply_argument_simplification(args)
    assert out.qlik_file == "app.qvf"


def test_out_alias_maps_to_output_dir():
    args = _base_args()
    args.out = "output/custom"
    out = _apply_argument_simplification(args)
    assert out.output_dir == "output/custom"
