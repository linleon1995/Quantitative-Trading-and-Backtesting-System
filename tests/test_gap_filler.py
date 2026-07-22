# tests/test_gap_filler.py
from unittest.mock import MagicMock

import pandas as pd

from src.data_source.gap_filler import GapFiller


def _raw_kline_row(open_time_ms: int) -> list:
    """Minimal Binance REST kline row."""
    return [
        open_time_ms,   # open_time
        "1.0",          # open
        "1.0",          # high
        "1.0",          # low
        "1.0",          # close
        "1.0",          # volume
        open_time_ms + 59_999,  # close_time
        "1.0",          # quote_asset_volume
        10,             # number_of_trades
        "0.5",          # taker_buy_base
        "0.5",          # taker_buy_quote
        "0",            # unused
    ]


def test_no_gap_skips_api(tmp_path):
    """If last_timestamp is within 2 intervals of now, no API call is made."""
    api = MagicMock()
    storage = MagicMock()
    storage.get_last_timestamp.return_value = int(
        (pd.Timestamp.utcnow() - pd.Timedelta(seconds=30)).value // 1_000_000
    )
    filler = GapFiller(api=api, storage=storage, gap_threshold_intervals=2)
    filler.fill("BTCUSDT", "1m")
    api.get_futures_klines.assert_not_called()


def test_fills_gap_with_single_batch():
    """A small gap triggers one API call and one storage.append."""
    api = MagicMock()
    storage = MagicMock()
    # last stored: 10 minutes ago
    ten_min_ago_ms = int(
        (pd.Timestamp.utcnow() - pd.Timedelta(minutes=10)).value // 1_000_000
    )
    storage.get_last_timestamp.return_value = ten_min_ago_ms

    rows = [_raw_kline_row(ten_min_ago_ms + i * 60_000) for i in range(1, 11)]
    api.get_futures_klines.return_value = rows

    filler = GapFiller(api=api, storage=storage, gap_threshold_intervals=2)
    filler.fill("BTCUSDT", "1m")

    api.get_futures_klines.assert_called_once()
    storage.append.assert_called_once()
    # Verify the DataFrame passed to append has 10 rows
    df_arg = storage.append.call_args[0][2]
    assert len(df_arg) == 10


def test_paginates_when_more_than_1000_rows():
    """A large gap triggers multiple API calls (1000 rows per page)."""
    api = MagicMock()
    storage = MagicMock()
    # last stored: 30 hours ago (1800 minutes → 2 pages of 1000/800)
    thirty_h_ago_ms = int(
        (pd.Timestamp.utcnow() - pd.Timedelta(hours=30)).value // 1_000_000
    )
    storage.get_last_timestamp.return_value = thirty_h_ago_ms

    def _side_effect(symbol, interval, startTime, endTime, limit):
        start = startTime
        count = min(limit, 1000)
        return [_raw_kline_row(start + i * 60_000) for i in range(count)]

    api.get_futures_klines.side_effect = _side_effect

    filler = GapFiller(api=api, storage=storage, gap_threshold_intervals=2)
    filler.fill("BTCUSDT", "1m")

    assert api.get_futures_klines.call_count >= 2


def test_no_data_does_full_backfill():
    """When storage has no data (None), backfill from a default lookback."""
    api = MagicMock()
    storage = MagicMock()
    storage.get_last_timestamp.return_value = None
    rows = [_raw_kline_row(1_700_000_000_000 + i * 60_000) for i in range(10)]
    api.get_futures_klines.return_value = rows

    filler = GapFiller(api=api, storage=storage, gap_threshold_intervals=2,
                       default_lookback_hours=1)
    filler.fill("BTCUSDT", "1m")
    api.get_futures_klines.assert_called()
    storage.append.assert_called()
