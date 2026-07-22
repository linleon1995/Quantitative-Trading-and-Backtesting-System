# src/data_source/data_reconciliation.py
"""DataReconciliation: run-to-completion gap reconciliation across symbols.

For each (symbol, interval) it reads the last-written checkpoint (ArcticDB's
last stored timestamp, via GapFiller/KlineStorage) and fills the gap up to
now. Per-symbol failures are isolated — one bad symbol does not abort the
batch — and surfaced in a structured ReconcileReport so a caller (k8s Job /
initContainer / DataCollector startup) can decide whether to release live
consumption.

See docs/superpowers/specs/2026-07-23-data-reconciliation-design.md
"""
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from src.data_source.gap_filler import FillResult, GapFiller

logger = logging.getLogger(__name__)


class ReconcileStatus(str, Enum):
    UP_TO_DATE = "up_to_date"              # gap within threshold, nothing fetched
    FILLED = "filled"                      # gap after existing data was filled
    BACKFILLED_FRESH = "backfilled_fresh"  # no prior data, default lookback backfilled
    FAILED = "failed"                      # an error occurred while filling


@dataclass(frozen=True)
class ReconcileResult:
    symbol: str
    interval: str
    last_written_ms: int | None
    target_ms: int
    rows_written: int
    status: ReconcileStatus
    error: str | None = None


@dataclass(frozen=True)
class ReconcileReport:
    results: list[ReconcileResult]

    @property
    def ok(self) -> bool:
        """True when no symbol failed reconciliation."""
        return all(r.status is not ReconcileStatus.FAILED for r in self.results)

    @property
    def total_rows(self) -> int:
        return sum(r.rows_written for r in self.results)

    def failures(self) -> list[ReconcileResult]:
        return [r for r in self.results if r.status is ReconcileStatus.FAILED]


def _status_from_fill(fill: FillResult) -> ReconcileStatus:
    if fill.skipped:
        return ReconcileStatus.UP_TO_DATE
    if fill.fresh:
        return ReconcileStatus.BACKFILLED_FRESH
    return ReconcileStatus.FILLED


class DataReconciliation:
    """Orchestrates GapFiller across symbols and reports the outcome."""

    def __init__(self, gap_filler: GapFiller) -> None:
        self._filler = gap_filler

    def reconcile(self, symbol: str, interval: str) -> ReconcileResult:
        """Reconcile one symbol. Never raises — failures become FAILED results."""
        try:
            fill = self._filler.fill(symbol, interval)
        except Exception as exc:  # isolate per-symbol failure
            logger.error(
                "reconcile %s/%s failed: %s", symbol, interval, exc, exc_info=True
            )
            return ReconcileResult(
                symbol=symbol,
                interval=interval,
                last_written_ms=None,
                target_ms=0,
                rows_written=0,
                status=ReconcileStatus.FAILED,
                error=str(exc),
            )
        return ReconcileResult(
            symbol=symbol,
            interval=interval,
            last_written_ms=fill.last_ms,
            target_ms=fill.target_ms,
            rows_written=fill.rows_written,
            status=_status_from_fill(fill),
        )

    def reconcile_all(self, symbols: Iterable[str], interval: str) -> ReconcileReport:
        """Reconcile every symbol; returns a report even if some fail."""
        results = [self.reconcile(symbol, interval) for symbol in symbols]
        report = ReconcileReport(results)
        logger.info(
            "reconcile_all done: %d symbols, %d rows written, ok=%s",
            len(results),
            report.total_rows,
            report.ok,
        )
        return report
