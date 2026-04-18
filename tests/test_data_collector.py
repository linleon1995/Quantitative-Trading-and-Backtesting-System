# tests/test_data_collector.py
from unittest.mock import MagicMock, patch, call
import pytest
from src.data_source.data_collector import DataCollector


def _make_kafka_msg(symbol: str, interval: str, open_time: int) -> MagicMock:
    """Simulate a kafka-python ConsumerRecord with the new tick format."""
    msg = MagicMock()
    msg.value = {
        "symbol": symbol,
        "interval": interval,
        "open_time": open_time,
        "open": 1.0,
        "high": 1.1,
        "low": 0.9,
        "close": 1.05,
        "volume": 100.0,
        "close_time": open_time + 59_999,
    }
    return msg


def test_gap_fill_runs_for_each_symbol_on_startup():
    gap_filler = MagicMock()
    storage = MagicMock()
    collector = DataCollector(
        gap_filler=gap_filler,
        storage=storage,
        symbols=["BTCUSDT", "ETHUSDT"],
        interval="1m",
        kafka_topic="binance_kline",
        kafka_servers=["kafka:9092"],
    )
    collector.startup_fill()
    assert gap_filler.fill.call_count == 2
    gap_filler.fill.assert_any_call("BTCUSDT", "1m")
    gap_filler.fill.assert_any_call("ETHUSDT", "1m")


def test_process_message_appends_to_storage():
    gap_filler = MagicMock()
    storage = MagicMock()
    collector = DataCollector(
        gap_filler=gap_filler,
        storage=storage,
        symbols=["BTCUSDT"],
        interval="1m",
        kafka_topic="binance_kline",
        kafka_servers=["kafka:9092"],
    )
    msg = _make_kafka_msg("BTCUSDT", "1m", 1_700_000_000_000)
    collector._process_message(msg)
    storage.append.assert_called_once()
    args = storage.append.call_args[0]
    assert args[0] == "BTCUSDT"
    assert args[1] == "1m"


def test_process_message_ignores_unknown_symbol():
    """Messages for symbols not in the configured list are dropped silently."""
    gap_filler = MagicMock()
    storage = MagicMock()
    collector = DataCollector(
        gap_filler=gap_filler,
        storage=storage,
        symbols=["BTCUSDT"],
        interval="1m",
        kafka_topic="binance_kline",
        kafka_servers=["kafka:9092"],
    )
    msg = _make_kafka_msg("XRPUSDT", "1m", 1_700_000_000_000)
    collector._process_message(msg)
    storage.append.assert_not_called()
