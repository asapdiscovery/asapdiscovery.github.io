"""Tests for protocols-export/convert.py."""

import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

spec = importlib.util.spec_from_file_location("convert", REPO / "protocols-export" / "convert.py")
convert = importlib.util.module_from_spec(spec)
spec.loader.exec_module(convert)


@pytest.mark.parametrize("url, expected", [
    ("https://www.protocols.io/view/foo-abc123/v3", "https://www.protocols.io/view/foo-abc123"),
    ("https://www.protocols.io/view/foo-abc123/v12/", "https://www.protocols.io/view/foo-abc123"),
    ("https://www.protocols.io/view/foo-abc123", "https://www.protocols.io/view/foo-abc123"),
])
def test_base_url(url, expected):
    assert convert.base_url(url) == expected


def test_latest_version_skips_gaps():
    row = {"version_1_published_on": "2024-01-01", "version_3_published_on": "2024-03-01"}
    assert convert.latest_version(row) == 3


def test_events_one_per_published_version():
    row = {
        "version_1_published_on": "2024-10-29 15:21:47",
        "version_1_doi": "dx.doi.org/10.17504/protocols.io.abc/v1",
        "version_2_published_on": "2025-06-04 13:52:09",
        "version_2_doi": "https://doi.org/10.17504/protocols.io.abc/v2",
    }
    assert convert.events_of(row) == [
        {"date": "2024-10-29", "description": "Published on protocols.io (doi:10.17504/protocols.io.abc/v1)"},
        {"date": "2025-06-04", "description": "Version 2 published on protocols.io (doi:10.17504/protocols.io.abc/v2)"},
    ]


def test_committed_yaml_matches_converter(tmp_path, monkeypatch):
    """data/outputs/protocols.yaml must be what convert.py produces from the newest export.

    Catches hand edits that the next refresh would silently overwrite.
    """
    committed = convert.PROTOCOLS_YAML.read_text()
    for name in ("protocols.yaml", "taxonomy.yaml"):
        src = convert.PROTOCOLS_YAML if name == "protocols.yaml" else convert.TAXONOMY
        shutil.copy(src, tmp_path / name)
    monkeypatch.setattr(convert, "PROTOCOLS_YAML", tmp_path / "protocols.yaml")
    monkeypatch.setattr(convert, "TAXONOMY", tmp_path / "taxonomy.yaml")
    monkeypatch.setattr(convert, "REPO", tmp_path)
    export = sorted(convert.EXPORTS.glob("*.csv"))[-1]
    local_export = tmp_path / export.name
    shutil.copy(export, local_export)
    monkeypatch.setattr(sys, "argv", ["convert.py", "--export", str(local_export)])

    convert.main()

    assert (tmp_path / "protocols.yaml").read_text() == committed, (
        "protocols.yaml differs from convert.py output; edit taxonomy.yaml or "
        "author-aliases.yaml and re-run protocols-export/convert.py instead of hand-editing"
    )
