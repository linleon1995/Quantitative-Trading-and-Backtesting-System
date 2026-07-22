# src/data_source/data_collector.py
"""DataCollector: startup gap-fill + live Kafka ingestion.

Startup sequence per symbol:
  1. GapFiller.fill(symbol, interval)  — backfills any historical gap
  2. KafkaConsumer loop               — appends each closed candle

Kafka messages must use the full OHLCV format emitted by the updated
binanace_producer.py (Task 3): {symbol, interval, open_time, open, high,
low, close, volume, close_time}
"""
import logging
from typing import Any

import pandas as pd
from kafka import KafkaConsumer

from src.data_process.kline_storage import KlineStorage
from src.data_source.data_reconciliation import DataReconciliation, ReconcileReport

logger = logging.getLogger(__name__)


class DataCollector:
    """Collects and persists kline data from Kafka with reconciliation on startup."""

    def __init__(
        self,
        reconciliation: DataReconciliation,
        storage: KlineStorage,
        symbols: list[str],
        interval: str,
        kafka_topic: str,
        kafka_servers: list[str],
    ) -> None:
        self._recon = reconciliation
        self._storage = storage
        self._symbols = set(symbols)
        self._interval = interval
        self._topic = kafka_topic
        self._servers = kafka_servers

    # ── startup ──────────────────────────────────────────────────────────────

    def startup_fill(self) -> ReconcileReport:
        """Reconcile every configured symbol before live consumption.

        Returns the ReconcileReport so the caller can gate run() on report.ok.
        Call before run().
        """
        logger.info(f"[startup] reconciling {len(self._symbols)} symbols /{self._interval}")
        report = self._recon.reconcile_all(self._symbols, self._interval)
        if not report.ok:
            logger.warning(
                "[startup] reconciliation had failures: %s",
                [r.symbol for r in report.failures()],
            )
        return report

    # ── live loop ─────────────────────────────────────────────────────────────

    def run(self) -> None:
        """Blocking loop: consume Kafka and append closed candles to storage.

        Call startup_fill() first. This method does not return unless an
        unrecoverable exception occurs.
        """
        consumer = KafkaConsumer(
            self._topic,
            bootstrap_servers=self._servers,
            value_deserializer=lambda b: __import__("json").loads(b.decode("utf-8")),
            auto_offset_reset="latest",
            enable_auto_commit=True,
        )
        logger.info(f"DataCollector: consuming topic '{self._topic}'")
        for msg in consumer:
            try:
                self._process_message(msg)
            except Exception as exc:
                logger.error(f"Failed to process message: {exc}", exc_info=True)

    # ── internal ─────────────────────────────────────────────────────────────

    def _process_message(self, msg: Any) -> None:
        tick = msg.value
        symbol: str = tick.get("symbol", "")
        interval: str = tick.get("interval", "")

        if symbol not in self._symbols:
            return
        if interval != self._interval:
            return

        df = _tick_to_dataframe(tick)
        self._storage.append(symbol, interval, df)
        logger.debug(f"Stored {symbol} {interval} open_time={tick['open_time']}")


def _tick_to_dataframe(tick: dict) -> pd.DataFrame:
    """Convert a single closed-candle tick dict to a one-row DataFrame."""
    open_time_ms = int(tick["open_time"])
    df = pd.DataFrame([{
        "open_time":   open_time_ms,
        "open_price":  float(tick["open"]),
        "high_price":  float(tick["high"]),
        "low_price":   float(tick["low"]),
        "close_price": float(tick["close"]),
        "volume":      float(tick["volume"]),
        "close_time":  int(tick["close_time"]),
    }])
    df["open_datetime"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    return df.set_index("open_datetime")
