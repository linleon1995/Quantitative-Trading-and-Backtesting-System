# tests/test_data_reconciliation.py
from unittest.mock import MagicMock

from src.data_source.data_reconciliation import (
    DataReconciliation,
    ReconcileStatus,
)
from src.data_source.gap_filler import FillResult


def _filler_returning(fill_result: FillResult) -> MagicMock:
    filler = MagicMock()
    filler.fill.return_value = fill_result
    return filler


# ── reconcile(): status mapping ──────────────────────────────────────────────

def test_reconcile_up_to_date_when_skipped():
    filler = _filler_returning(
        FillResult("BTCUSDT", "1m", last_ms=1000, target_ms=2000,
                   rows_written=0, skipped=True, fresh=False)
    )
    result = DataReconciliation(filler).reconcile("BTCUSDT", "1m")

    assert result.status is ReconcileStatus.UP_TO_DATE
    assert result.rows_written == 0
    assert result.last_written_ms == 1000
    assert result.error is None


def test_reconcile_filled_when_rows_written():
    filler = _filler_returning(
        FillResult("BTCUSDT", "1m", last_ms=1000, target_ms=8000,
                   rows_written=42, skipped=False, fresh=False)
    )
    result = DataReconciliation(filler).reconcile("BTCUSDT", "1m")

    assert result.status is ReconcileStatus.FILLED
    assert result.rows_written == 42
    assert result.target_ms == 8000


def test_reconcile_backfilled_fresh_when_no_prior_data():
    filler = _filler_returning(
        FillResult("BTCUSDT", "1m", last_ms=None, target_ms=8000,
                   rows_written=60, skipped=False, fresh=True)
    )
    result = DataReconciliation(filler).reconcile("BTCUSDT", "1m")

    assert result.status is ReconcileStatus.BACKFILLED_FRESH
    assert result.last_written_ms is None
    assert result.rows_written == 60


def test_reconcile_failed_isolates_exception():
    """A raising GapFiller.fill becomes a FAILED result, not a propagated exception."""
    filler = MagicMock()
    filler.fill.side_effect = RuntimeError("REST 500")

    result = DataReconciliation(filler).reconcile("BTCUSDT", "1m")

    assert result.status is ReconcileStatus.FAILED
    assert result.error == "REST 500"
    assert result.rows_written == 0


# ── reconcile_all(): batch behaviour ─────────────────────────────────────────

def test_reconcile_all_isolates_one_failure():
    """One symbol failing must not abort the batch; report reflects it."""
    filler = MagicMock()

    def _fill(symbol, interval):
        if symbol == "ETHUSDT":
            raise ValueError("boom")
        return FillResult(symbol, interval, last_ms=1000, target_ms=2000,
                          rows_written=5, skipped=False, fresh=False)

    filler.fill.side_effect = _fill
    report = DataReconciliation(filler).reconcile_all(
        ["BTCUSDT", "ETHUSDT", "SOLUSDT"], "1m"
    )

    assert len(report.results) == 3
    assert report.ok is False
    failed = report.failures()
    assert [r.symbol for r in failed] == ["ETHUSDT"]
    assert report.total_rows == 10  # BTC(5) + SOL(5), ETH contributes 0


def test_reconcile_all_ok_when_all_succeed():
    filler = _filler_returning(
        FillResult("X", "1m", last_ms=1000, target_ms=2000,
                   rows_written=3, skipped=False, fresh=False)
    )
    report = DataReconciliation(filler).reconcile_all(["A", "B"], "1m")

    assert report.ok is True
    assert report.failures() == []
    assert report.total_rows == 6
