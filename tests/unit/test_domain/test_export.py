"""Tests for Export entity (BACKLOG.md T-024)."""

from __future__ import annotations

import uuid

import pytest

from finfluencer.domain.entities import EntityId, Export, ExportFormat


def _report_id() -> EntityId:
    return EntityId(uuid.uuid4())


def test_construction_succeeds_with_all_required_fields() -> None:
    export = Export(report_id=_report_id(), report_version=1, format=ExportFormat.PDF)
    assert export.report_version == 1
    assert export.format is ExportFormat.PDF


def test_cannot_construct_without_report_id() -> None:
    with pytest.raises(ValueError, match="report_id"):
        Export(report_id=None, report_version=1, format=ExportFormat.PDF)


def test_cannot_construct_with_report_version_below_one() -> None:
    with pytest.raises(ValueError, match="report_version"):
        Export(report_id=_report_id(), report_version=0, format=ExportFormat.PDF)


def test_cannot_construct_without_format() -> None:
    with pytest.raises(ValueError, match="format"):
        Export(report_id=_report_id(), report_version=1, format=None)


def test_only_pdf_format_exists() -> None:
    # section 8.4: Word is explicitly v1.x, not implemented in this task's scope.
    assert [f.value for f in ExportFormat] == ["pdf"]


def test_no_pinning_field_is_settable_after_construction() -> None:
    export = Export(report_id=_report_id(), report_version=1, format=ExportFormat.PDF)
    for field_name in ("report_id", "report_version", "format"):
        with pytest.raises(AttributeError):
            setattr(export, field_name, "anything")


def test_export_has_no_mutating_methods_at_all() -> None:
    # section 10.1, line 608: "an Export is a rendering of a specific, already-immutable
    # Report version; there's nothing to mutate."
    export = Export(report_id=_report_id(), report_version=1, format=ExportFormat.PDF)
    public_callables = [
        name for name in dir(export)
        if not name.startswith("_") and callable(getattr(export, name))
    ]
    assert public_callables == []
