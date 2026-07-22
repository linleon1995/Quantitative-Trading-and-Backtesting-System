# tests/test_smoke_timeseries.py
"""Smoke tests for ArcticDB time-series storage.

Coverage:
  1. 時間段已存在資料 — overlapping insert produces no duplicates and updates values
  2. 插入時間的精細度驗證 — millisecond-level timestamps survive round-trip intact
  3. update / list API — update() replaces values; has_symbol() / list_symbols() reflect state
"""
import pytest
import pandas as pd

from src.data_source.create_backtest_database import ArcticDBOperator
from src.data_process.kline_storage import KlineStorage


BASE_MS = 1_700_000_000_000  # 2023-11-14 22:13 UTC — arbitrary stable anchor
MINUTE_MS = 60_000


def _make_df(open_times_ms: list[int], price_start: float = 1.0) -> pd.DataFrame:
    n = len(open_times_ms)
    df = pd.DataFrame({
        "open_time": open_times_ms,
        "open_price": [float(price_start + i) for i in range(n)],
        "high_price": 1.0,
        "low_price": 1.0,
        "close_price": 1.0,
        "volume": 100.0,
    })
    df["open_datetime"] = pd.to_datetime(df["open_time"], unit="ms")
    return df.set_index("open_datetime")


@pytest.fixture
def operator(tmp_path):
    return ArcticDBOperator(url=f"lmdb://{tmp_path}/db", lib_name="smoke")


@pytest.fixture
def storage(operator):
    return KlineStorage(operator)


# ── 1. 時間段已存在資料 ───────────────────────────────────────────────────────

def test_overlapping_insert_no_duplicate_rows(operator):
    """Insert T0-T4, then T3-T7: result must have 8 unique rows, no duplicates."""
    first  = [BASE_MS + i * MINUTE_MS for i in range(5)]     # T0..T4
    second = [BASE_MS + i * MINUTE_MS for i in range(3, 8)]  # T3..T7

    operator.add("BTCUSDT_1m", _make_df(first, price_start=1.0))
    operator.add("BTCUSDT_1m", _make_df(second, price_start=100.0))

    df = operator.read(
        "BTCUSDT_1m",
        pd.Timestamp(BASE_MS, unit="ms"),
        pd.Timestamp(BASE_MS + 8 * MINUTE_MS, unit="ms"),
    ).data

    assert len(df) == 8, f"Expected 8 rows, got {len(df)}"
    assert df.index.is_unique, "Index has duplicate timestamps"


def test_overlapping_insert_updates_existing_values(operator):
    """Rows in the overlap range must reflect the second write's values, not the first."""
    first  = [BASE_MS + i * MINUTE_MS for i in range(5)]
    second = [BASE_MS + i * MINUTE_MS for i in range(3, 8)]

    operator.add("ETHUSDT_1m", _make_df(first, price_start=1.0))
    operator.add("ETHUSDT_1m", _make_df(second, price_start=100.0))

    overlap_df = operator.read(
        "ETHUSDT_1m",
        pd.Timestamp(BASE_MS + 3 * MINUTE_MS, unit="ms"),
        pd.Timestamp(BASE_MS + 4 * MINUTE_MS, unit="ms"),
    ).data

    assert (overlap_df["open_price"] >= 100.0).all(), (
        f"Overlap rows should be overwritten by second insert, got: {overlap_df['open_price'].tolist()}"
    )


# ── 2. 插入時間的精細度驗證 ─────────────────────────────────────────────────

def test_millisecond_precision_preserved_round_trip(storage):
    """Timestamps with sub-minute ms offsets must survive write → read unchanged."""
    offsets = [0, 999, 1_000, 59_999, 60_000, 3_600_001]
    times_ms = [BASE_MS + o for o in offsets]

    storage.append("ETHUSDT", "1s", _make_df(times_ms))
    result_df = storage.read("ETHUSDT", "1s", BASE_MS, BASE_MS + offsets[-1])

    retrieved_ms = [int(ts.value // 1_000_000) for ts in result_df.index]
    assert retrieved_ms == times_ms, (
        f"Precision mismatch.\nExpected: {times_ms}\nGot:      {retrieved_ms}"
    )


def test_get_last_timestamp_exact_ms(storage):
    """get_last_timestamp() must return the exact ms of the most recent row."""
    exact_ms = BASE_MS + 12_345  # non-round offset to catch rounding bugs
    storage.append("SOLUSDT", "1s", _make_df([BASE_MS, exact_ms]))
    assert storage.get_last_timestamp("SOLUSDT", "1s") == exact_ms


# ── 3. update / list API ─────────────────────────────────────────────────────

def test_update_overwrites_matching_rows(operator):
    """update() must replace open_price values for every row in the given range."""
    times = [BASE_MS + i * MINUTE_MS for i in range(3)]

    operator.write("XRPUSDT_1m", _make_df(times, price_start=10.0))
    operator.update("XRPUSDT_1m", _make_df(times, price_start=99.0))

    df = operator.read(
        "XRPUSDT_1m",
        pd.Timestamp(times[0], unit="ms"),
        pd.Timestamp(times[-1], unit="ms"),
    ).data

    assert list(df["open_price"]) == pytest.approx([99.0, 100.0, 101.0]), (
        f"update() did not overwrite values: {df['open_price'].tolist()}"
    )


def test_has_symbol_false_before_write(operator):
    assert operator.has_symbol("GHOST_1m") is False


def test_has_symbol_true_after_write(operator):
    operator.write("BNBUSDT_1m", _make_df([BASE_MS]))
    assert operator.has_symbol("BNBUSDT_1m") is True


def test_list_symbols_includes_all_written(operator):
    """All written symbols must appear in the library's list_symbols() output."""
    symbols = ["ADAUSDT_1m", "DOTUSDT_5m", "LINKUSDT_15m"]
    for sym in symbols:
        operator.write(sym, _make_df([BASE_MS]))

    listed = operator.ac[operator.lib_name].list_symbols()
    missing = [s for s in symbols if s not in listed]
    assert not missing, f"Symbols missing from list_symbols(): {missing}"
