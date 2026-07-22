# tests/test_data_reconciliation_main.py
from unittest.mock import MagicMock

from src.data_source import data_reconciliation_main as main_mod
from src.data_source.data_reconciliation import (
    ReconcileReport,
    ReconcileResult,
    ReconcileStatus,
)


def _report(*statuses: ReconcileStatus) -> ReconcileReport:
    return ReconcileReport([
        ReconcileResult(f"SYM{i}", "1m", None, 0, 0, status)
        for i, status in enumerate(statuses)
    ])


def _patch_build(monkeypatch, report: ReconcileReport) -> MagicMock:
    reconciliation = MagicMock()
    reconciliation.reconcile_all.return_value = report
    monkeypatch.setattr(
        main_mod, "build_reconciliation",
        lambda: (reconciliation, ["SYM0"], "1m"),
    )
    return reconciliation


def test_main_exits_zero_when_all_ok(monkeypatch):
    _patch_build(monkeypatch, _report(ReconcileStatus.FILLED, ReconcileStatus.UP_TO_DATE))
    assert main_mod.main() == 0


def test_main_exits_one_when_any_failed(monkeypatch):
    _patch_build(monkeypatch, _report(ReconcileStatus.FILLED, ReconcileStatus.FAILED))
    assert main_mod.main() == 1
