# src/data_source/data_reconciliation_main.py
"""Entry point for the data-reconciliation service (k8s Job / initContainer).

Runs a one-shot reconciliation for the configured symbols and exits:
  exit 0 — every symbol reconciled successfully (release live consumption)
  exit 1 — at least one symbol failed (do not release; inspect logs)

Configure via environment variables (same names as data_collector_main).

Usage:
    python -m src.data_source.data_reconciliation_main
"""
import logging
import os
import sys

from src.client.binance_api import BinanceAPI
from src.data_process.kline_storage import KlineStorage
from src.data_source.create_backtest_database import ArcticDBOperator
from src.data_source.data_reconciliation import DataReconciliation
from src.data_source.gap_filler import GapFiller

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

ARCTIC_URL = os.environ.get("ARCTIC_URL", "lmdb://arctic_database")
ARCTIC_LIB = os.environ.get("ARCTIC_LIB", "klines")
INTERVAL = os.environ.get("KLINE_INTERVAL", "1m")
SYMBOLS_ENV = os.environ.get("SYMBOLS", "BTCUSDT,ETHUSDT")


def build_reconciliation() -> tuple[DataReconciliation, list[str], str]:
    """Assemble the reconciliation stack from environment configuration."""
    symbols = [s.strip() for s in SYMBOLS_ENV.split(",") if s.strip()]
    api = BinanceAPI()
    operator = ArcticDBOperator(url=ARCTIC_URL, lib_name=ARCTIC_LIB)
    storage = KlineStorage(operator)
    reconciliation = DataReconciliation(GapFiller(api=api, storage=storage))
    return reconciliation, symbols, INTERVAL


def main() -> int:
    reconciliation, symbols, interval = build_reconciliation()
    report = reconciliation.reconcile_all(symbols, interval)

    for r in report.results:
        logger.info(
            "%s/%s: %s (rows=%d, last=%s, target=%s)",
            r.symbol, r.interval, r.status.value, r.rows_written,
            r.last_written_ms, r.target_ms,
        )

    if not report.ok:
        logger.error(
            "reconciliation failed for: %s",
            [f"{r.symbol}: {r.error}" for r in report.failures()],
        )
        return 1

    logger.info("reconciliation complete: %d rows written", report.total_rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
