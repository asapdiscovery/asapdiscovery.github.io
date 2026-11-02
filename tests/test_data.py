"""Integrity checks on data/ that rppr/generate-rppr.py relies on.

The site renders whatever is in data/, so these mistakes do not break the Hugo build;
they silently drop outputs from the RPPR progress reports instead.
"""

import datetime
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
COMPONENTS = set(yaml.safe_load((REPO / "rppr" / "specific-aims.yaml").read_text()))
ALIASES = yaml.safe_load((REPO / "rppr" / "component-aliases.yaml").read_text())

OUTPUT_FILES = sorted((REPO / "data" / "outputs").glob("*.yaml"))
PUBLICATIONS = REPO / "data" / "publications" / "publications.yaml"


def outputs_in(path):
    """Entries of a data file, whether it is keyed by ID or a plain list."""
    data = yaml.safe_load(path.read_text())
    entries = data.values() if isinstance(data, dict) else data
    return [e for e in entries if isinstance(e, dict)]


def entry_id(path, entry):
    return f"{path.relative_to(REPO)}: {entry.get('name') or entry.get('title')}"


ATTRIBUTED = [
    pytest.param(path, entry, id=entry_id(path, entry))
    for path in OUTPUT_FILES + [PUBLICATIONS]
    for entry in outputs_in(path)
]


def test_aliases_point_at_components():
    for name, targets in ALIASES.items():
        assert name not in COMPONENTS, f"{name} is already a component"
        assert set(targets) <= COMPONENTS, f"{name} -> {targets}"


@pytest.mark.parametrize("path, entry", ATTRIBUTED)
def test_component_names_are_known(path, entry):
    """Every projects/cores name must be an RPPR component or a listed alias."""
    names = (entry.get("projects") or []) + (entry.get("cores") or [])
    unknown = [n for n in names if n not in COMPONENTS and n not in ALIASES]
    assert not unknown, (
        f"not in rppr/specific-aims.yaml or rppr/component-aliases.yaml: {unknown}"
    )


@pytest.mark.parametrize("path, entry", ATTRIBUTED)
def test_event_dates_are_iso(path, entry):
    for event in entry.get("events") or []:
        datetime.date.fromisoformat(str(event["date"]))
        assert event.get("description"), f"event on {event['date']} has no description"


def test_every_protocol_has_events():
    protocols = outputs_in(REPO / "data" / "outputs" / "protocols.yaml")
    missing = [p["name"] for p in protocols if not p.get("events")]
    assert not missing
