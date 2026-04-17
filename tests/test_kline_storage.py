# tests/test_kline_storage.py
from unittest.mock import MagicMock
import pandas as pd
import pytest
from src.data_process.kline_storage import KlineStorage


def _make_df(open_times_ms: list[int]) -> pd.DataFrame:
    """Return a minimal OHLCV DataFrame indexed by open_datetime."""
    df = pd.DataFrame({
        "open_time": open_times_ms,
        "open_price": 1.0,
        "high_price": 1.0,
        "low_price": 1.0,
        "close_price": 1.0,
        "volume": 1.0,
    })
    df["open_datetime"] = pd.to_datetime(df["open_time"], unit="ms")
    return df.set_index("open_datetime")


def test_append_uses_correct_key():
    operator = MagicMock()
    storage = KlineStorage(operator)
    df = _make_df([1_000_000])
    storage.append("BTCUSDT", "1m", df)
    operator.add.assert_called_once_with("BTCUSDT_1m", df)


def test_get_last_timestamp_returns_none_when_no_data():
    operator = MagicMock()
    operator.has_symbol = MagicMock(return_value=False)
    storage = KlineStorage(operator)
    assert storage.get_last_timestamp("BTCUSDT", "1m") is None


def test_get_last_timestamp_returns_ms_integer():
    operator = MagicMock()
    operator.has_symbol = MagicMock(return_value=True)
    mock_result = MagicMock()
    ts_ms = 1_700_000_000_000
    mock_result.data = _make_df([ts_ms])
    operator.read_last = MagicMock(return_value=mock_result)
    storage = KlineStorage(operator)
    result = storage.get_last_timestamp("BTCUSDT", "1m")
    assert result == ts_ms


def test_read_delegates_to_operator():
    operator = MagicMock()
    mock_result = MagicMock()
    mock_result.data = _make_df([1_000_000])
    operator.read = MagicMock(return_value=mock_result)
    storage = KlineStorage(operator)
    result = storage.read("BTCUSDT", "1m", 0, 9_999_999)
    operator.read.assert_called_once_with(
        "BTCUSDT_1m",
        pd.Timestamp(0, unit="ms"),
        pd.Timestamp(9_999_999, unit="ms"),
    )
    assert result is mock_result.data
