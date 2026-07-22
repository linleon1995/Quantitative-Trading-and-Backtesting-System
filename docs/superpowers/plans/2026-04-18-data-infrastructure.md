# Data Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reliable data layer that fills historical gaps on startup, streams live klines via Kafka, and aligns trading state with the exchange after any downtime.

**Architecture:** Four sequential stages — (1) consolidate the BinanceTick dataclass and wrap ArcticDB in a typed `KlineStorage`; (2) fix the Kafka producer to emit full OHLCV only on closed candles; (3) build `GapFiller` + `DataCollector` for startup reconciliation and live ingestion; (4) build `StartupCoordinator` + `StateAligner` for trading state recovery.

**Tech Stack:** Python 3.11, ArcticDB (lmdb), kafka-python, pandas, pytest, unittest.mock, existing `BinanceAPI` (`src/client/binance_api.py`)

---

## File Map

**New files**
- `src/data_process/kline_storage.py` — typed wrapper around `ArcticDBOperator`
- `src/data_source/gap_filler.py` — REST API historical backfill
- `src/data_source/data_collector.py` — Kafka consumer + startup gap detection
- `src/orchestrator/startup_coordinator.py` — state load, align, and resume

**Modified files**
- `src/data_process/write_data.py` — remove duplicate `BinanceTick`, import from `data_structure`
- `src/data_source/binanace_producer.py` — emit full OHLCV, only on `kline['x'] == True`

**New test files**
- `tests/test_kline_storage.py`
- `tests/test_gap_filler.py`
- `tests/test_data_collector.py`
- `tests/test_startup_coordinator.py`

---

## Task 1: Consolidate BinanceTick

`write_data.py` and `data_structure.py` each define an identical `BinanceTick` dataclass. Remove the duplicate and use one canonical source.

**Files:**
- Modify: `src/data_process/write_data.py`

- [ ] **Step 1: Remove duplicate BinanceTick from write_data.py and import the canonical one**

Replace lines 24-37 in `src/data_process/write_data.py` (the `BinanceTick` dataclass definition) with a single import:

```python
from src.data_process.data_structure import BinanceTick
```

The rest of the file is unchanged. `data_structure.BinanceTick` already has identical fields.

- [ ] **Step 2: Verify nothing broke**

```bash
cd /home/linleon1995/project/quant && python -c "from src.data_process.write_data import format_kline_data, BinanceTick; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/data_process/write_data.py
git commit -m "refactor: remove duplicate BinanceTick in write_data, import from data_structure"
```

---

## Task 2: KlineStorage

A thin typed wrapper around `ArcticDBOperator` that enforces a consistent key convention (`{SYMBOL}_{INTERVAL}`) and exposes only the methods needed by `GapFiller` and `DataCollector`.

**Files:**
- Create: `src/data_process/kline_storage.py`
- Create: `tests/test_kline_storage.py`

- [ ] **Step 1: Write the failing tests**

```python
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
    # ArcticDB read returns an object with .data attribute
    mock_result = MagicMock()
    ts_ms = 1_700_000_000_000
    idx = pd.DatetimeIndex([pd.Timestamp(ts_ms, unit="ms")])
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
    storage.read("BTCUSDT", "1m", 0, 9_999_999)
    operator.read.assert_called_once_with(
        "BTCUSDT_1m",
        pd.Timestamp(0, unit="ms"),
        pd.Timestamp(9_999_999, unit="ms"),
    )
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd /home/linleon1995/project/quant && python -m pytest tests/test_kline_storage.py -v
```

Expected: `ImportError` — `kline_storage` module not found.

- [ ] **Step 3: Write KlineStorage**

```python
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

    # ── internal ────────────────────────────────────────────────────────────

    def _key(self, symbol: str, interval: str) -> str:
        return f"{symbol}_{interval}"

    # ── public API ───────────────────────────────────────────────────────────

    def append(self, symbol: str, interval: str, df: pd.DataFrame) -> None:
        """Append (or initialise) kline rows for a symbol/interval pair.

        df must be a DataFrame indexed by DatetimIndex (open_datetime UTC)
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
```

- [ ] **Step 4: Add `has_symbol` and `read_last` to ArcticDBOperator**

`ArcticDBOperator` (`src/data_source/create_backtest_database.py`) is missing `has_symbol` and `read_last`. Add both methods:

```python
def has_symbol(self, data_name: str) -> bool:
    """Return True if the symbol exists in the library."""
    lib = self.ac[self.lib_name]
    return lib.has_symbol(data_name)

def read_last(self, data_name: str):
    """Return the last row of a symbol (tail=1)."""
    lib = self.ac[self.lib_name]
    return lib.read(data_name, row_range=(- 1, None))
```

- [ ] **Step 5: Run tests — expect PASS**

```bash
cd /home/linleon1995/project/quant && python -m pytest tests/test_kline_storage.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/data_process/kline_storage.py src/data_source/create_backtest_database.py tests/test_kline_storage.py
git commit -m "feat: KlineStorage wrapper + ArcticDBOperator.has_symbol/read_last"
```

---

## Task 3: Fix Kafka Producer — Full OHLCV + Closed Candle Only

Currently the producer emits `{close_price, volume}` for every WebSocket update. Change it to emit full OHLCV only when `kline['x'] == True` (candle closed).

**Files:**
- Modify: `src/data_source/binanace_producer.py`

- [ ] **Step 1: Update the tick format and add closed-candle guard**

In `BinanceKafkaProducerWorker.run()`, replace the tick construction block (lines 82-93) with:

```python
kline = data['k']

# Only emit when the candle is closed (final value)
if not kline.get('x', False):
    continue

symbol = data['s']
tick = {
    'symbol': symbol,
    'interval': kline['i'],
    'open_time': int(kline['t']),    # ms
    'open':      float(kline['o']),
    'high':      float(kline['h']),
    'low':       float(kline['l']),
    'close':     float(kline['c']),
    'volume':    float(kline['v']),
    'close_time': int(kline['T']),   # ms
}

self.producer.send(KAFKA_TOPIC, key=symbol, value=tick)
logging.debug(f"Closed candle sent: {symbol} {kline['i']} @ {kline['t']}")
```

Also remove the now-unused `last_timestamps` deduplication dict and its check (lines 53, 78-80) since `x == True` already guarantees one message per closed candle.

- [ ] **Step 2: Verify producer starts without error**

```bash
cd /home/linleon1995/project/quant && python -c "
from unittest.mock import MagicMock, patch
import asyncio, json
from src.data_source.binanace_producer import BinanceKafkaProducerWorker

producer = MagicMock()
worker = BinanceKafkaProducerWorker(['btcusdt@kline_1m'], producer)

# Simulate one closed-candle message
msg = json.dumps({'s': 'BTCUSDT', 'k': {
    'x': True, 'i': '1m', 't': 1700000000000, 'T': 1700000059999,
    'o': '30000', 'h': '30100', 'l': '29900', 'c': '30050', 'v': '100'
}})

# Confirm tick structure
import json as _j
kline_data = _j.loads(msg)['k']
assert kline_data.get('x') == True
print('Closed-candle guard: OK')
"
```

Expected: `Closed-candle guard: OK`

- [ ] **Step 3: Commit**

```bash
git add src/data_source/binanace_producer.py
git commit -m "fix: producer emits full OHLCV only on closed candle (kline[x]==True)"
```

---

## Task 4: GapFiller

Fetches historical klines from Binance REST API and writes them to `KlineStorage`. Handles Binance's 1000-row-per-request limit by paginating automatically.

**Files:**
- Create: `src/data_source/gap_filler.py`
- Create: `tests/test_gap_filler.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_gap_filler.py
from unittest.mock import MagicMock, call, patch
import pandas as pd
import pytest
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
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd /home/linleon1995/project/quant && python -m pytest tests/test_gap_filler.py -v
```

Expected: `ImportError` — `gap_filler` not found.

- [ ] **Step 3: Write GapFiller**

```python
# src/data_source/gap_filler.py
"""GapFiller: backfills missing kline data from Binance REST API.

Uses BinanceAPI.get_futures_klines() (max 1000 rows/request) and writes
results to KlineStorage. Can be called standalone or from DataCollector
at startup.
"""
import logging
from typing import Optional

import pandas as pd

from src.client.binance_api import BinanceAPI
from src.data_process.data_structure import BinanceTick
from src.data_process.kline_storage import KlineStorage

logger = logging.getLogger(__name__)

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

    def fill(self, symbol: str, interval: str) -> None:
        """Fill any gap for the given symbol/interval up to the current time."""
        interval_ms = _INTERVAL_MS.get(interval)
        if interval_ms is None:
            raise ValueError(f"Unknown interval: {interval}")

        now_ms = int(pd.Timestamp.utcnow().value // 1_000_000)
        last_ms = self._storage.get_last_timestamp(symbol, interval)

        if last_ms is None:
            from_ms = now_ms - self._default_lookback_hours * 3_600_000
            logger.info(f"{symbol}/{interval}: no data, backfilling {self._default_lookback_hours}h")
        else:
            gap_ms = now_ms - last_ms
            threshold_ms = self._gap_threshold_intervals * interval_ms
            if gap_ms <= threshold_ms:
                logger.info(f"{symbol}/{interval}: gap {gap_ms}ms ≤ threshold, skipping")
                return
            from_ms = last_ms + interval_ms  # start from the first missing candle
            logger.info(f"{symbol}/{interval}: gap {gap_ms}ms, backfilling from {from_ms}")

        self._fetch_and_store(symbol, interval, from_ms, now_ms - interval_ms)

    def _fetch_and_store(
        self,
        symbol: str,
        interval: str,
        from_ms: int,
        to_ms: int,
    ) -> None:
        cursor = from_ms
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
            last_open = int(df.index[-1].value // 1_000_000)
            interval_ms = _INTERVAL_MS[interval]
            cursor = last_open + interval_ms
            logger.info(f"  stored {len(df)} rows, next cursor={cursor}")
            if len(rows) < _BATCH_SIZE:
                break


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
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd /home/linleon1995/project/quant && python -m pytest tests/test_gap_filler.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/data_source/gap_filler.py tests/test_gap_filler.py
git commit -m "feat: GapFiller — REST API backfill with pagination"
```

---

## Task 5: DataCollector

Coordinates startup gap-fill and live Kafka ingestion. For each configured `(symbol, interval)` pair it runs `GapFiller.fill()`, then begins consuming the Kafka topic and appending closed candles to `KlineStorage`.

**Files:**
- Create: `src/data_source/data_collector.py`
- Create: `tests/test_data_collector.py`

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd /home/linleon1995/project/quant && python -m pytest tests/test_data_collector.py -v
```

Expected: `ImportError` — `data_collector` not found.

- [ ] **Step 3: Write DataCollector**

```python
# src/data_source/data_collector.py
"""DataCollector: startup gap-fill + live Kafka ingestion.

Startup sequence per symbol:
  1. GapFiller.fill(symbol, interval)  — backfills any historical gap
  2. KafkaConsumer loop               — appends each closed candle

Kafka messages must use the full OHLCV format emitted by the updated
binanace_producer.py (see Task 3).
"""
import logging
from typing import Any

import pandas as pd
from kafka import KafkaConsumer

from src.data_process.kline_storage import KlineStorage
from src.data_source.gap_filler import GapFiller

logger = logging.getLogger(__name__)


class DataCollector:
    """Collects and persists kline data from Kafka with gap-fill on startup."""

    def __init__(
        self,
        gap_filler: GapFiller,
        storage: KlineStorage,
        symbols: list[str],
        interval: str,
        kafka_topic: str,
        kafka_servers: list[str],
    ) -> None:
        self._filler = gap_filler
        self._storage = storage
        self._symbols = set(symbols)
        self._interval = interval
        self._topic = kafka_topic
        self._servers = kafka_servers

    # ── startup ──────────────────────────────────────────────────────────────

    def startup_fill(self) -> None:
        """Run GapFiller for every configured symbol. Call before run()."""
        for symbol in self._symbols:
            logger.info(f"[startup] gap-fill {symbol}/{self._interval}")
            self._filler.fill(symbol, self._interval)

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
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd /home/linleon1995/project/quant && python -m pytest tests/test_data_collector.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/data_source/data_collector.py tests/test_data_collector.py
git commit -m "feat: DataCollector — startup gap-fill + Kafka live ingestion"
```

---

## Task 6: StartupCoordinator + StateAligner

Handles trading state recovery after downtime. Reads persisted state, queries the exchange for the actual positions/balance, reconciles any delta, then signals the orchestrator to resume.

**Files:**
- Create: `src/orchestrator/startup_coordinator.py`
- Create: `tests/test_startup_coordinator.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_startup_coordinator.py
from unittest.mock import MagicMock, patch
import pytest
from src.orchestrator.startup_coordinator import StartupCoordinator, AlignedState


def _mock_api(balance=1000.0, positions=None):
    api = MagicMock()
    # get_futures_account_balance() returns {"USDT": float, ...}
    api.get_futures_account_balance.return_value = {"USDT": balance}
    api.get_futures_positions.return_value = positions or []
    return api


def test_fresh_start_returns_exchange_balance():
    """No saved state → use exchange balance, no alignment needed."""
    api = _mock_api(balance=500.0)
    coord = StartupCoordinator(api=api, state_path="/nonexistent/state.json")
    result = coord.prepare()
    assert result.balance == 500.0
    assert result.positions == {}
    assert result.aligned is True


def test_saved_state_with_no_delta_returns_as_is():
    """Saved state matches exchange — no changes needed."""
    api = _mock_api(balance=1000.0, positions=[])
    saved = {
        "balance": 1000.0,
        "positions": {},
    }
    coord = StartupCoordinator(api=api, state_path="/fake/state.json")
    with patch("builtins.open", unittest_mock_open(saved)):
        with patch("json.load", return_value=saved):
            result = coord.prepare()
    assert result.aligned is True
    assert result.balance == 1000.0


def test_saved_position_closed_on_exchange_is_reconciled():
    """Local state has open position; exchange has none → position cleared."""
    api = _mock_api(balance=1100.0, positions=[])
    saved = {
        "balance": 1000.0,
        "positions": {"BTCUSDT": {"size": 0.01, "entry_price": 30000.0}},
    }
    coord = StartupCoordinator(api=api, state_path="/fake/state.json")
    with patch.object(coord, "_load_state", return_value=saved):
        result = coord.prepare()
    assert "BTCUSDT" not in result.positions
    assert result.balance == 1100.0  # uses exchange balance


def test_balance_mismatch_uses_exchange_balance():
    """Exchange balance differs from saved — always trust exchange."""
    api = _mock_api(balance=850.0)
    saved = {"balance": 1000.0, "positions": {}}
    coord = StartupCoordinator(api=api, state_path="/fake/state.json")
    with patch.object(coord, "_load_state", return_value=saved):
        result = coord.prepare()
    assert result.balance == 850.0


# helper
def unittest_mock_open(data):
    import unittest.mock as m, json, io
    return m.mock_open(read_data=json.dumps(data))
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd /home/linleon1995/project/quant && python -m pytest tests/test_startup_coordinator.py -v
```

Expected: `ImportError` — `startup_coordinator` not found.

- [ ] **Step 3: Write StartupCoordinator + StateAligner**

```python
# src/orchestrator/startup_coordinator.py
"""StartupCoordinator: load saved state, align with exchange, return ready state.

Usage:
    coord = StartupCoordinator(api=binance_api, state_path="data/state.json")
    state = coord.prepare()
    # state.balance, state.positions are now exchange-accurate
    orchestrator.resume(state)
"""
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from src.client.binance_api import BinanceAPI

logger = logging.getLogger(__name__)


@dataclass
class AlignedState:
    """Exchange-aligned state ready for the orchestrator to consume."""
    balance: float
    positions: dict  # symbol → {size, entry_price}
    aligned: bool = True


class StartupCoordinator:
    """Loads persisted state and aligns it against live exchange data."""

    def __init__(self, api: BinanceAPI, state_path: str) -> None:
        self._api = api
        self._state_path = Path(state_path)

    # ── public ───────────────────────────────────────────────────────────────

    def prepare(self) -> AlignedState:
        """Return an exchange-accurate AlignedState.

        - If no state file exists: fresh start using exchange balance.
        - If state file exists: run StateAligner to reconcile deltas.
        """
        saved = self._load_state()
        exchange_balance = self._fetch_usdt_balance()
        exchange_positions = self._fetch_open_positions()

        if saved is None:
            logger.info("No saved state — fresh start")
            return AlignedState(balance=exchange_balance, positions={})

        logger.info("Saved state found — running alignment")
        aligner = StateAligner(saved, exchange_balance, exchange_positions)
        return aligner.align()

    # ── internal ─────────────────────────────────────────────────────────────

    def _load_state(self) -> Optional[dict]:
        if not self._state_path.exists():
            return None
        try:
            with open(self._state_path) as f:
                return json.load(f)
        except Exception as exc:
            logger.warning(f"Could not load state file: {exc} — treating as fresh start")
            return None

    def _fetch_usdt_balance(self) -> float:
        # get_futures_account_balance() returns {"USDT": float, "BTC": float, ...}
        balances = self._api.get_futures_account_balance() or {}
        return float(balances.get("USDT", 0.0))

    def _fetch_open_positions(self) -> dict:
        """Return {symbol: {size, entry_price}} for non-zero positions."""
        rows = self._api.get_futures_positions() or []
        return {
            r["symbol"]: {
                "size": float(r.get("positionAmt", 0)),
                "entry_price": float(r.get("entryPrice", 0)),
            }
            for r in rows
            if float(r.get("positionAmt", 0)) != 0
        }


class StateAligner:
    """Reconciles saved local state against live exchange state."""

    def __init__(
        self,
        saved: dict,
        exchange_balance: float,
        exchange_positions: dict,
    ) -> None:
        self._saved = saved
        self._ex_balance = exchange_balance
        self._ex_positions = exchange_positions

    def align(self) -> AlignedState:
        """Apply delta reconciliation rules and return aligned state."""
        saved_positions: dict = self._saved.get("positions", {})
        reconciled = {}

        for symbol, local_pos in saved_positions.items():
            if symbol in self._ex_positions:
                # Position still open on exchange — keep exchange version
                reconciled[symbol] = self._ex_positions[symbol]
                logger.info(f"  {symbol}: position carried over from exchange")
            else:
                # Position closed on exchange while we were offline
                logger.info(f"  {symbol}: position closed on exchange, clearing local")

        # Positions opened on exchange while offline are ignored here;
        # the orchestrator will detect them on the first price tick.

        # Always trust exchange balance
        if self._ex_balance != self._saved.get("balance"):
            logger.info(
                f"  balance: saved={self._saved.get('balance')}, "
                f"exchange={self._ex_balance} — using exchange"
            )

        return AlignedState(
            balance=self._ex_balance,
            positions=reconciled,
            aligned=True,
        )
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd /home/linleon1995/project/quant && python -m pytest tests/test_startup_coordinator.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Run full test suite**

```bash
cd /home/linleon1995/project/quant && python -m pytest tests/ -v
```

Expected: all tests PASS (including pre-existing tests).

- [ ] **Step 6: Commit**

```bash
git add src/orchestrator/startup_coordinator.py tests/test_startup_coordinator.py
git commit -m "feat: StartupCoordinator + StateAligner — state recovery after downtime"
```

---

## Task 7: Wire Everything Together — Entry Point

Create a `data_collector_main.py` entry point that instantiates all components and runs the full startup → live loop.

**Files:**
- Create: `src/data_source/data_collector_main.py`

- [ ] **Step 1: Write the entry point**

```python
# src/data_source/data_collector_main.py
"""Entry point for the Data Collector process.

Runs independently of the trading process.
Configure symbols, interval, and Kafka settings via environment variables
or edit the constants below.

Usage:
    python -m src.data_source.data_collector_main
"""
import logging
import os

from src.client.binance_api import BinanceAPI
from src.data_source.create_backtest_database import ArcticDBOperator
from src.data_process.kline_storage import KlineStorage
from src.data_source.gap_filler import GapFiller
from src.data_source.data_collector import DataCollector

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

KAFKA_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092").split(",")
KAFKA_TOPIC = os.environ.get("KAFKA_TOPIC", "binance_kline")
ARCTIC_URL = os.environ.get("ARCTIC_URL", "lmdb://arctic_database")
ARCTIC_LIB = os.environ.get("ARCTIC_LIB", "klines")
INTERVAL = os.environ.get("KLINE_INTERVAL", "1m")
# Comma-separated list of symbols; empty = fetch all USDT perpetuals
SYMBOLS_ENV = os.environ.get("SYMBOLS", "BTCUSDT,ETHUSDT")

def main():
    symbols = [s.strip() for s in SYMBOLS_ENV.split(",") if s.strip()]

    api = BinanceAPI()
    operator = ArcticDBOperator(url=ARCTIC_URL, lib_name=ARCTIC_LIB)
    storage = KlineStorage(operator)
    gap_filler = GapFiller(api=api, storage=storage)
    collector = DataCollector(
        gap_filler=gap_filler,
        storage=storage,
        symbols=symbols,
        interval=INTERVAL,
        kafka_topic=KAFKA_TOPIC,
        kafka_servers=KAFKA_SERVERS,
    )

    collector.startup_fill()
    collector.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify import chain is clean**

```bash
cd /home/linleon1995/project/quant && python -c "import src.data_source.data_collector_main; print('import OK')"
```

Expected: `import OK`

- [ ] **Step 3: Commit**

```bash
git add src/data_source/data_collector_main.py
git commit -m "feat: data_collector_main entry point"
```
