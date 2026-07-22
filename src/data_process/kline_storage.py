# src/data_process/kline_storage.py
"""Typed wrapper around ArcticDBOperator for kline time-series storage.

Key convention: "{SYMBOL}_{INTERVAL}", e.g. "BTCUSDT_1m".
All timestamps are UTC milliseconds (int).
"""
import pandas as pd

from src.data_source.create_backtest_database import ArcticDBOperator


class KlineStorage:
    """Wraps ArcticDBOperator with a kline-specific interface."""

    def __init__(self, operator: ArcticDBOperator) -> None:
        self._op = operator

    def _key(self, symbol: str, interval: str) -> str:
        return f"{symbol}_{interval}"

    def append(self, symbol: str, interval: str, df: pd.DataFrame) -> None:
        """Append (or initialise) kline rows for a symbol/interval pair.

        df must be a DataFrame indexed by DatetimeIndex (open_datetime UTC)
        with at minimum columns: open_price, high_price, low_price,
        close_price, volume.
        """
        self._op.add(self._key(symbol, interval), df)

    def get_last_timestamp(self, symbol: str, interval: str) -> int | None:
        """Return the open_time (ms) of the most recent stored kline, or None."""
        key = self._key(symbol, interval)
        if not self._op.has_symbol(key):
            return None
        result = self._op.read_last(key)
        last_idx: pd.Timestamp = result.data.index[-1]
        return int(last_idx.value // 1_000_000)  # ns → ms

    def read(
        self,
        symbol: str,
        interval: str,
        start_ms: int,
        end_ms: int,
    ) -> pd.DataFrame:
        """Read klines for the given ms timestamp range (inclusive)."""
        result = self._op.read(
            self._key(symbol, interval),
            pd.Timestamp(start_ms, unit="ms"),
            pd.Timestamp(end_ms, unit="ms"),
        )
        return result.data
