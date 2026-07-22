# src/data_source/gap_filler.py
"""GapFiller: backfills missing kline data from Binance REST API.

Uses BinanceAPI.get_futures_klines() (max 1000 rows/request) and writes
results to KlineStorage. Can be called standalone or from DataCollector
at startup.
"""
import logging
from dataclasses import dataclass

import pandas as pd

from src.client.binance_api import BinanceAPI
from src.data_process.data_structure import BinanceTick
from src.data_process.kline_storage import KlineStorage

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FillResult:
    """Outcome of a single GapFiller.fill() call."""

    symbol: str
    interval: str
    last_ms: int | None   # checkpoint (None = no prior data)
    target_ms: int        # filled up to this open_time (now aligned to last closed candle)
    rows_written: int
    skipped: bool         # gap within threshold, no API call made
    fresh: bool           # no prior data, default_lookback backfill performed

# Binance interval string → milliseconds
_INTERVAL_MS: dict[str, int] = {
    "1m":  60_000,
    "3m":  180_000,
    "5m":  300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h":  3_600_000,
    "4h":  14_400_000,
    "1d":  86_400_000,
}
_BATCH_SIZE = 1000


class GapFiller:
    """Fills historical kline gaps for a (symbol, interval) pair."""

    def __init__(
        self,
        api: BinanceAPI,
        storage: KlineStorage,
        gap_threshold_intervals: int = 2,
        default_lookback_hours: int = 24,
    ) -> None:
        self._api = api
        self._storage = storage
        self._gap_threshold_intervals = gap_threshold_intervals
        self._default_lookback_hours = default_lookback_hours

    def fill(self, symbol: str, interval: str) -> FillResult:
        """Fill any gap for the given symbol/interval up to the current time.

        Returns a FillResult describing what happened (rows written, range,
        whether it was skipped or a fresh backfill).
        """
        interval_ms = _INTERVAL_MS.get(interval)
        if interval_ms is None:
            raise ValueError(f"Unknown interval: {interval}")

        now_ms = int(pd.Timestamp.utcnow().value // 1_000_000)
        target_ms = now_ms - interval_ms  # up to the last closed candle
        last_ms = self._storage.get_last_timestamp(symbol, interval)

        if last_ms is None:
            from_ms = now_ms - self._default_lookback_hours * 3_600_000
            logger.info(f"{symbol}/{interval}: no data, backfilling {self._default_lookback_hours}h")
            rows = self._fetch_and_store(symbol, interval, from_ms, target_ms)
            return FillResult(symbol, interval, None, target_ms, rows, skipped=False, fresh=True)

        gap_ms = now_ms - last_ms
        threshold_ms = self._gap_threshold_intervals * interval_ms
        if gap_ms <= threshold_ms:
            logger.info(f"{symbol}/{interval}: gap {gap_ms}ms ≤ threshold, skipping")
            return FillResult(symbol, interval, last_ms, target_ms, 0, skipped=True, fresh=False)

        from_ms = last_ms + interval_ms  # start from the first missing candle
        logger.info(f"{symbol}/{interval}: gap {gap_ms}ms, backfilling from {from_ms}")
        rows = self._fetch_and_store(symbol, interval, from_ms, target_ms)
        return FillResult(symbol, interval, last_ms, target_ms, rows, skipped=False, fresh=False)

    def _fetch_and_store(
        self,
        symbol: str,
        interval: str,
        from_ms: int,
        to_ms: int,
    ) -> int:
        """Fetch klines page by page and append them. Returns total rows written."""
        total = 0
        cursor = from_ms
        interval_ms = _INTERVAL_MS[interval]
        while cursor <= to_ms:
            rows = self._api.get_futures_klines(
                symbol=symbol,
                interval=interval,
                startTime=cursor,
                endTime=to_ms,
                limit=_BATCH_SIZE,
            )
            if not rows:
                break
            df = _rows_to_dataframe(rows)
            self._storage.append(symbol, interval, df)
            total += len(df)
            last_open = int(df.index[-1].value // 1_000_000)
            cursor = last_open + interval_ms
            logger.info(f"  stored {len(df)} rows, next cursor={cursor}")
            if len(rows) < _BATCH_SIZE:
                break
        return total


def _rows_to_dataframe(rows: list) -> pd.DataFrame:
    """Convert raw Binance kline rows to a DataFrame indexed by open_datetime."""
    from dataclasses import fields as dc_fields
    tick_fields = [f.name for f in dc_fields(BinanceTick)]
    df = pd.DataFrame(rows, columns=tick_fields)
    df["open_time"] = df["open_time"].astype("int64")
    df["open_price"] = df["open_price"].astype("float64")
    df["high_price"] = df["high_price"].astype("float64")
    df["low_price"] = df["low_price"].astype("float64")
    df["close_price"] = df["close_price"].astype("float64")
    df["volume"] = df["volume"].astype("float64")
    df["open_datetime"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    return df.set_index("open_datetime")
