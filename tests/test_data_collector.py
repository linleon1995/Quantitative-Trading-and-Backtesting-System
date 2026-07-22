# tests/test_data_collector.py
from unittest.mock import MagicMock

from src.data_source.data_collector import DataCollector
from src.data_source.data_reconciliation import (
    ReconcileReport,
    ReconcileResult,
    ReconcileStatus,
)


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


def _ok_report(symbols: list[str]) -> ReconcileReport:
    return ReconcileReport([
        ReconcileResult(s, "1m", None, 0, 0, ReconcileStatus.UP_TO_DATE)
        for s in symbols
    ])


def test_startup_fill_delegates_to_reconciliation():
    reconciliation = MagicMock()
    reconciliation.reconcile_all.return_value = _ok_report(["BTCUSDT", "ETHUSDT"])
    storage = MagicMock()
    collector = DataCollector(
        reconciliation=reconciliation,
        storage=storage,
        symbols=["BTCUSDT", "ETHUSDT"],
        interval="1m",
        kafka_topic="binance_kline",
        kafka_servers=["kafka:9092"],
    )
    report = collector.startup_fill()

    reconciliation.reconcile_all.assert_called_once()
    called_symbols, called_interval = reconciliation.reconcile_all.call_args[0]
    assert set(called_symbols) == {"BTCUSDT", "ETHUSDT"}
    assert called_interval == "1m"
    assert report.ok is True


def test_process_message_appends_to_storage():
    reconciliation = MagicMock()
    storage = MagicMock()
    collector = DataCollector(
        reconciliation=reconciliation,
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
    reconciliation = MagicMock()
    storage = MagicMock()
    collector = DataCollector(
        reconciliation=reconciliation,
        storage=storage,
        symbols=["BTCUSDT"],
        interval="1m",
        kafka_topic="binance_kline",
        kafka_servers=["kafka:9092"],
    )
    msg = _make_kafka_msg("XRPUSDT", "1m", 1_700_000_000_000)
    collector._process_message(msg)
    storage.append.assert_not_called()
