# Strategy 狀態持久化與回復機制 實作計畫

> **給 AI 工作者：** 必要 Sub-Skill：使用 superpowers:subagent-driven-development（建議）或 superpowers:executing-plans 逐任務實作此計畫。步驟使用核取方塊（`- [ ]`）語法追蹤進度。

**目標：** 為交易策略設計可跨策略共用的狀態持久化與回復機制，包含斷線補齊（gap replay）功能，確保程式重啟後能從上次中斷點接續運行。

**架構：**
- `StrategyState`（抽象基底 ABC）定義共用欄位，各策略子類定義自身中間狀態。
- `Stateful` Protocol 規範策略必須實作 `get_state()` / `restore_state()`。
- `StrategyStateManager` 負責 JSON 檔案讀寫（每 symbol 一個檔，atomic write），與策略邏輯完全解耦。
- 回復時自動補抓斷線期間的歷史 K 線並以靜默模式 replay，更新指標但不執行信號。持倉不存入 state，由 exchange API 另行同步。

**技術棧：** Python 3.10+、dataclasses、abc、json、pytest、Binance klines API（BinanceTrader / BinanceAPI）

---

## 檔案結構規劃

| 操作 | 路徑 | 職責 |
|------|------|------|
| 建立 | `src/strategies/strategy_state.py` | `StrategyState` ABC、`DynamicBreakoutState`、`Stateful` Protocol、`STATE_REGISTRY` |
| 建立 | `src/state/__init__.py` | 空 |
| 建立 | `src/state/state_manager.py` | `StrategyStateManager`（JSON 讀寫、atomic write） |
| 修改 | `src/strategies/dynamic_breakout_atx.py` | 新增 `start_time` 參數；實作 `get_state()` / `restore_state()` |
| 修改 | `src/trader/binance_trader.py` | `get_futures_klines` 新增 `start_time_ms` 參數 |
| 修改 | `src/config/trading_config.py` | `LiveTradingConfig` 新增 `state_dir`；`load_config_from_env` 讀取 `STATE_DIR` |
| 修改 | `live_trading.py` | 啟動時回復狀態 + gap replay；每 tick 存狀態 |
| 修改 | `.env.template` | 新增 `STATE_DIR=state` |
| 建立 | `tests/strategies/test_strategy_state.py` | StrategyState 序列化/反序列化測試 |
| 建立 | `tests/state/__init__.py` | 空 |
| 建立 | `tests/state/test_state_manager.py` | StateManager 讀寫、atomic write、容錯測試 |
| 建立 | `tests/strategies/test_dynamic_breakout_state.py` | get_state / restore_state 整合測試 |
| 建立 | `tests/strategies/test_gap_replay.py` | gap replay 信號抑制 + 指標更新測試 |

---

## 任務 1：定義 StrategyState ABC 與 DynamicBreakoutState

**檔案：**
- 建立：`src/strategies/strategy_state.py`
- 測試：`tests/strategies/test_strategy_state.py`

- [ ] **步驟 1：撰寫失敗測試**

```python
# tests/strategies/test_strategy_state.py
import pytest
from datetime import datetime, timezone
from src.strategies.strategy_state import DynamicBreakoutState, StrategyState


def test_dynamic_breakout_state_to_dict():
    """DynamicBreakoutState 必須能序列化為 dict 供 JSON 儲存。"""
    start = datetime(2026, 3, 18, 0, 0, 0, tzinfo=timezone.utc)
    interrupted = datetime(2026, 3, 19, 14, 30, 0, tzinfo=timezone.utc)
    state = DynamicBreakoutState(
        symbol="BTCUSDT",
        start_time=start,
        interrupted_at=interrupted,
        mean_atr=12.5,
        mean_vol=340.2,
        mean_adx=18.1,
        high=85000.0,
        low=82000.0,
        short_high=84500.0,
        short_low=83000.0,
        prices=[83000.0, 84000.0, 85000.0],
        volumes=[100.0, 120.0, 110.0],
        atr_values=[12.0, 12.5, 13.0],
        adx_values=[18.0, 18.1, 18.2],
        num_trade=5,
        total_earn=120.5,
    )
    d = state.to_dict()
    assert d["strategy_type"] == "DynamicBreakoutState"
    assert d["symbol"] == "BTCUSDT"
    assert d["mean_atr"] == 12.5
    assert d["start_time"] == "2026-03-18T00:00:00+00:00"
    assert d["interrupted_at"] == "2026-03-19T14:30:00+00:00"
    assert d["prices"] == [83000.0, 84000.0, 85000.0]


def test_dynamic_breakout_state_roundtrip():
    """from_dict(to_dict()) 必須還原完整 state 物件，包含 None 欄位。"""
    start = datetime(2026, 3, 18, 0, 0, 0, tzinfo=timezone.utc)
    interrupted = datetime(2026, 3, 19, 14, 30, 0, tzinfo=timezone.utc)
    original = DynamicBreakoutState(
        symbol="ETHUSDT",
        start_time=start,
        interrupted_at=interrupted,
        mean_atr=5.0,
        mean_vol=200.0,
        mean_adx=None,
        high=3000.0,
        low=2900.0,
        short_high=2950.0,
        short_low=2910.0,
        prices=[2900.0, 2950.0],
        volumes=[200.0, 210.0],
        atr_values=[4.5, 5.0],
        adx_values=[],
        num_trade=0,
        total_earn=0.0,
    )
    restored = DynamicBreakoutState.from_dict(original.to_dict())
    assert restored.symbol == original.symbol
    assert restored.mean_atr == original.mean_atr
    assert restored.mean_adx is None
    assert restored.start_time == original.start_time
    assert restored.interrupted_at == original.interrupted_at
    assert restored.prices == original.prices


def test_strategy_state_is_abstract():
    """StrategyState 本身不可直接實例化（ABC）。"""
    with pytest.raises(TypeError):
        StrategyState(symbol="X",
                      start_time=datetime.now(tz=timezone.utc),
                      interrupted_at=datetime.now(tz=timezone.utc))
```

- [ ] **步驟 2：執行測試確認失敗**

```bash
pytest tests/strategies/test_strategy_state.py -v
```
預期：ImportError，`strategy_state` 不存在

- [ ] **步驟 3：實作 strategy_state.py**

```python
# src/strategies/strategy_state.py
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List, Protocol, runtime_checkable


class StrategyState(ABC):
    """
    所有策略 State 的抽象基底。
    子類必須實作 to_dict() / from_dict()，並設定 strategy_type。
    """
    symbol: str
    start_time: datetime
    interrupted_at: datetime
    strategy_type: str

    @abstractmethod
    def to_dict(self) -> dict:
        ...

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict) -> "StrategyState":
        ...

    @staticmethod
    def _dt_to_str(dt: Optional[datetime]) -> Optional[str]:
        return dt.isoformat() if dt else None

    @staticmethod
    def _str_to_dt(s: Optional[str]) -> Optional[datetime]:
        return datetime.fromisoformat(s) if s else None


@dataclass
class DynamicBreakoutState(StrategyState):
    """DynamicBreakoutTrader 的中間狀態快照。"""

    # 共用欄位（手動宣告，因 StrategyState 不是 dataclass）
    symbol: str
    start_time: datetime
    interrupted_at: datetime

    # 計算中間結果（核心）
    mean_atr: Optional[float]
    mean_vol: Optional[float]
    mean_adx: Optional[float]
    high: Optional[float]
    low: Optional[float]
    short_high: float
    short_low: float

    # 滾動視窗資料（省去重算 ATR/ADX 初始化期）
    prices: List[float] = field(default_factory=list)
    volumes: List[float] = field(default_factory=list)
    atr_values: List[float] = field(default_factory=list)
    adx_values: List[float] = field(default_factory=list)

    # 統計
    num_trade: int = 0
    total_earn: float = 0.0

    def __post_init__(self):
        self.strategy_type = "DynamicBreakoutState"

    def to_dict(self) -> dict:
        return {
            "strategy_type": self.strategy_type,
            "symbol": self.symbol,
            "start_time": self._dt_to_str(self.start_time),
            "interrupted_at": self._dt_to_str(self.interrupted_at),
            "mean_atr": self.mean_atr,
            "mean_vol": self.mean_vol,
            "mean_adx": self.mean_adx,
            "high": self.high,
            "low": self.low,
            "short_high": self.short_high,
            "short_low": self.short_low,
            "prices": list(self.prices),
            "volumes": list(self.volumes),
            "atr_values": list(self.atr_values),
            "adx_values": list(self.adx_values),
            "num_trade": self.num_trade,
            "total_earn": self.total_earn,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DynamicBreakoutState":
        return cls(
            symbol=data["symbol"],
            start_time=cls._str_to_dt(data["start_time"]),
            interrupted_at=cls._str_to_dt(data["interrupted_at"]),
            mean_atr=data.get("mean_atr"),
            mean_vol=data.get("mean_vol"),
            mean_adx=data.get("mean_adx"),
            high=data.get("high"),
            low=data.get("low"),
            short_high=data.get("short_high", float('-inf')),
            short_low=data.get("short_low", float('inf')),
            prices=data.get("prices", []),
            volumes=data.get("volumes", []),
            atr_values=data.get("atr_values", []),
            adx_values=data.get("adx_values", []),
            num_trade=data.get("num_trade", 0),
            total_earn=data.get("total_earn", 0.0),
        )


# Registry：strategy_type 字串 → class（新增策略時在此登記）
STATE_REGISTRY: dict = {
    "DynamicBreakoutState": DynamicBreakoutState,
}


@runtime_checkable
class Stateful(Protocol):
    """策略若要支援狀態持久化，必須實作此 Protocol。"""

    def get_state(self) -> StrategyState:
        """回傳目前策略狀態快照。"""
        ...

    def restore_state(self, state: StrategyState) -> None:
        """從快照回復策略內部狀態（不觸發任何信號）。"""
        ...
```

- [ ] **步驟 4：執行測試確認通過**

```bash
pytest tests/strategies/test_strategy_state.py -v
```
預期：3 tests PASS

- [ ] **步驟 5：提交**

```bash
git add src/strategies/strategy_state.py tests/strategies/test_strategy_state.py
git commit -m "feat: add StrategyState ABC + DynamicBreakoutState + Stateful protocol"
```

---

## 任務 2：DynamicBreakoutTrader 實作 Stateful Protocol

**檔案：**
- 修改：`src/strategies/dynamic_breakout_atx.py`
- 測試：`tests/strategies/test_dynamic_breakout_state.py`

- [ ] **步驟 1：撰寫失敗測試**

```python
# tests/strategies/test_dynamic_breakout_state.py
import pytest
from datetime import datetime, timezone, timedelta
from src.strategies.dynamic_breakout_atx import DynamicBreakoutTrader
from src.strategies.strategy_state import DynamicBreakoutState, Stateful

START_TIME = datetime(2026, 3, 18, 0, 0, 0, tzinfo=timezone.utc)


def _make_warmed_trader(num_ticks: int = 20) -> DynamicBreakoutTrader:
    """建立已暖機的 trader（indicators 已初始化）。"""
    trader = DynamicBreakoutTrader(
        symbol="BTCUSDT", lookback=14, atr_period=14, start_time=START_TIME
    )
    for i in range(num_ticks):
        trader.on_tick(
            START_TIME + timedelta(minutes=i),
            {'close_price': 85000.0 + i * 10, 'volume': 100.0 + i}
        )
    return trader


def test_stateful_protocol_compliance():
    """DynamicBreakoutTrader 必須符合 Stateful Protocol。"""
    trader = DynamicBreakoutTrader(symbol="BTCUSDT", start_time=START_TIME)
    assert isinstance(trader, Stateful)


def test_get_state_returns_dynamic_breakout_state():
    """get_state() 應回傳 DynamicBreakoutState，且核心欄位正確。"""
    trader = _make_warmed_trader()
    state = trader.get_state()
    assert isinstance(state, DynamicBreakoutState)
    assert state.symbol == "BTCUSDT"
    assert state.start_time == START_TIME
    assert state.mean_atr is not None
    assert state.mean_vol is not None
    assert len(state.prices) > 0
    assert state.interrupted_at is not None


def test_restore_state_recovers_indicators():
    """restore_state() 應還原所有 indicators 與統計。"""
    original = _make_warmed_trader()
    saved_state = original.get_state()

    new_trader = DynamicBreakoutTrader(symbol="BTCUSDT", start_time=START_TIME)
    new_trader.restore_state(saved_state)

    assert new_trader.mean_atr == original.mean_atr
    assert new_trader.mean_vol == original.mean_vol
    assert new_trader.high == original.high
    assert list(new_trader.prices) == list(original.prices)
    assert new_trader.num_trade == original.num_trade
    assert new_trader.start_time == original.start_time


def test_restore_state_does_not_emit_signals():
    """restore_state() 過程本身不應觸發任何 on_signal callback。"""
    signals = []
    original = _make_warmed_trader()
    saved_state = original.get_state()

    new_trader = DynamicBreakoutTrader(
        symbol="BTCUSDT",
        start_time=START_TIME,
        on_signal=lambda s: signals.append(s)
    )
    new_trader.restore_state(saved_state)
    assert signals == []
```

- [ ] **步驟 2：執行測試確認失敗**

```bash
pytest tests/strategies/test_dynamic_breakout_state.py -v
```
預期：FAIL，`DynamicBreakoutTrader.__init__` 不接受 `start_time` 參數

- [ ] **步驟 3：修改 DynamicBreakoutTrader**

在 `src/strategies/dynamic_breakout_atx.py` 的 `__init__` 加入：
```python
# 在 import 區加入
from datetime import datetime, timezone

# __init__ 參數列加入
start_time: Optional[datetime] = None,

# __init__ 內加入
self.start_time: Optional[datetime] = start_time
```

新增 `get_state()` 方法：
```python
def get_state(self) -> "DynamicBreakoutState":
    from src.strategies.strategy_state import DynamicBreakoutState
    now = datetime.now(tz=timezone.utc)
    return DynamicBreakoutState(
        symbol=self.symbol,
        start_time=self.start_time or now,
        interrupted_at=now,
        mean_atr=self.mean_atr,
        mean_vol=self.mean_vol,
        mean_adx=self.mean_adx,
        high=self.high,
        low=self.low,
        short_high=self.short_high,
        short_low=self.short_low,
        prices=list(self.prices),
        volumes=list(self.volumes),
        atr_values=list(self.atr_values),
        adx_values=list(self.adx_values),
        num_trade=self.num_trade,
        total_earn=self.total_earn,
    )
```

新增 `restore_state()` 方法（不觸發信號）：
```python
def restore_state(self, state: "DynamicBreakoutState") -> None:
    from collections import deque
    self.start_time = state.start_time
    self.mean_atr = state.mean_atr
    self.mean_vol = state.mean_vol
    self.mean_adx = state.mean_adx
    self.high = state.high
    self.low = state.low
    self.short_high = state.short_high
    self.short_low = state.short_low
    self.prices = deque(state.prices, maxlen=self.lookback)
    self.volumes = deque(state.volumes, maxlen=self.lookback)
    self.atr_values = deque(state.atr_values, maxlen=self.atr_period)
    self.adx_values = deque(state.adx_values, maxlen=self.adx_period)
    self.num_trade = state.num_trade
    self.total_earn = state.total_earn
    self.avg_earn = self.total_earn / self.num_trade if self.num_trade else 0.0
```

- [ ] **步驟 4：執行測試確認通過**

```bash
pytest tests/strategies/test_dynamic_breakout_state.py -v
```
預期：4 tests PASS

- [ ] **步驟 5：確認既有測試未受影響**

```bash
pytest tests/ -v -k "strategy"
```
預期：所有既有測試 PASS

- [ ] **步驟 6：提交**

```bash
git add src/strategies/dynamic_breakout_atx.py tests/strategies/test_dynamic_breakout_state.py
git commit -m "feat: implement Stateful protocol (get_state/restore_state) in DynamicBreakoutTrader"
```

---

## 任務 3：StrategyStateManager — JSON 讀寫（per-symbol 檔案）

**檔案：**
- 建立：`src/state/__init__.py`
- 建立：`src/state/state_manager.py`
- 測試：`tests/state/test_state_manager.py`

- [ ] **步驟 1：撰寫失敗測試**

```python
# tests/state/test_state_manager.py
import json
import os
import shutil
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from src.state.state_manager import StrategyStateManager
from src.strategies.strategy_state import DynamicBreakoutState

STATE_DIR = "tests/state/tmp_state"


@pytest.fixture(autouse=True)
def cleanup():
    yield
    if os.path.exists(STATE_DIR):
        shutil.rmtree(STATE_DIR)


def _make_state(symbol: str = "BTCUSDT") -> DynamicBreakoutState:
    return DynamicBreakoutState(
        symbol=symbol,
        start_time=datetime(2026, 3, 18, tzinfo=timezone.utc),
        interrupted_at=datetime(2026, 3, 19, 14, 30, tzinfo=timezone.utc),
        mean_atr=12.5, mean_vol=340.2, mean_adx=18.1,
        high=85000.0, low=82000.0, short_high=84500.0, short_low=83000.0,
        prices=[83000.0, 84000.0], volumes=[100.0, 120.0],
        atr_values=[12.0, 12.5], adx_values=[18.0],
        num_trade=3, total_earn=50.0,
    )


def test_save_creates_file():
    mgr = StrategyStateManager(state_dir=STATE_DIR)
    mgr.save(_make_state("BTCUSDT"))
    assert Path(f"{STATE_DIR}/BTCUSDT.json").exists()


def test_save_content_is_valid_json():
    mgr = StrategyStateManager(state_dir=STATE_DIR)
    mgr.save(_make_state("ETHUSDT"))
    with open(f"{STATE_DIR}/ETHUSDT.json") as f:
        data = json.load(f)
    assert data["strategy_type"] == "DynamicBreakoutState"
    assert data["symbol"] == "ETHUSDT"


def test_load_roundtrip():
    mgr = StrategyStateManager(state_dir=STATE_DIR)
    original = _make_state("SOLUSDT")
    mgr.save(original)
    loaded = mgr.load("SOLUSDT")
    assert loaded is not None
    assert isinstance(loaded, DynamicBreakoutState)
    assert loaded.symbol == "SOLUSDT"
    assert loaded.mean_atr == 12.5
    assert loaded.interrupted_at == original.interrupted_at


def test_load_returns_none_when_no_file():
    mgr = StrategyStateManager(state_dir=STATE_DIR)
    assert mgr.load("NONEXISTENT") is None


def test_load_returns_none_for_corrupted_json():
    """損壞的 JSON 檔應回傳 None，不拋出例外。"""
    mgr = StrategyStateManager(state_dir=STATE_DIR)
    path = Path(STATE_DIR) / "CORRUPT.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not valid json", encoding="utf-8")
    assert mgr.load("CORRUPT") is None


def test_load_returns_none_for_unknown_strategy_type():
    """未知的 strategy_type 應回傳 None（不 crash）。"""
    mgr = StrategyStateManager(state_dir=STATE_DIR)
    path = Path(STATE_DIR) / "XUSDT.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"strategy_type": "UnknownStrategy", "symbol": "XUSDT"}))
    assert mgr.load("XUSDT") is None


def test_save_is_atomic(tmp_path):
    """save() 應使用 atomic write（先寫 .tmp 再 rename）。"""
    mgr = StrategyStateManager(state_dir=str(tmp_path))
    state = _make_state("BNBUSDT")
    calls = []
    original_replace = os.replace

    with patch("src.state.state_manager.os.replace",
               side_effect=lambda src, dst: (calls.append((src, dst)),
                                             original_replace(src, dst))):
        mgr.save(state)

    assert len(calls) == 1
    src, dst = calls[0]
    assert src.endswith(".json.tmp")
    assert dst.endswith("BNBUSDT.json")
```

- [ ] **步驟 2：執行測試確認失敗**

```bash
pytest tests/state/test_state_manager.py -v
```
預期：ImportError，`state_manager` 不存在

- [ ] **步驟 3：實作 state_manager.py**

```python
# src/state/__init__.py
# （空）
```

```python
# src/state/state_manager.py
import json
import logging
import os
from pathlib import Path
from typing import Optional

from src.strategies.strategy_state import StrategyState, STATE_REGISTRY

logger = logging.getLogger(__name__)

BINANCE_KLINES_LIMIT = 1000  # Binance API 單次最大回傳筆數


class StrategyStateManager:
    """
    每個 symbol 一個 JSON 檔，存放路徑：{state_dir}/{symbol}.json。
    使用 atomic write（寫入 .tmp 再 os.replace）確保即使程式崩潰，
    現有狀態檔不會出現部分寫入損壞。
    """

    def __init__(self, state_dir: str = "state"):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, symbol: str) -> Path:
        return self.state_dir / f"{symbol}.json"

    def save(self, state: StrategyState) -> None:
        """將 state 序列化為 JSON 並 atomic write 到 {symbol}.json。"""
        target = self._path(state.symbol)
        tmp = target.with_suffix(".json.tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(state.to_dict(), f, ensure_ascii=False, indent=2)
            os.replace(tmp, target)
        except Exception:
            logger.exception("Failed to save state for %s", state.symbol)
            if tmp.exists():
                tmp.unlink(missing_ok=True)

    def load(self, symbol: str) -> Optional[StrategyState]:
        """
        讀取 {symbol}.json 並反序列化。
        - 檔案不存在 → None
        - strategy_type 未知 → log warning + None
        - JSON 損壞 → log exception + None
        """
        path = self._path(symbol)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            strategy_type = data.get("strategy_type")
            cls = STATE_REGISTRY.get(strategy_type)
            if cls is None:
                logger.warning("Unknown strategy_type '%s' for %s", strategy_type, symbol)
                return None
            return cls.from_dict(data)
        except Exception:
            logger.exception("Failed to load state for %s", symbol)
            return None
```

- [ ] **步驟 4：執行測試確認通過**

```bash
pytest tests/state/test_state_manager.py -v
```
預期：7 tests PASS

- [ ] **步驟 5：提交**

```bash
git add src/state/__init__.py src/state/state_manager.py \
        tests/state/__init__.py tests/state/test_state_manager.py
git commit -m "feat: add StrategyStateManager with per-symbol JSON atomic write"
```

---

## 任務 4：BinanceTrader 新增 start_time_ms 參數

**背景：** gap replay 需要抓取從 `interrupted_at` 開始的 K 線。現有
`BinanceTrader.get_futures_klines` 僅接受 `limit`，不接受起始時間；
而底層 `BinanceAPI.get_futures_klines` 已支援 `startTime`（epoch ms）。

**檔案：**
- 修改：`src/trader/binance_trader.py`（line 152-163）

- [ ] **步驟 1：修改 `get_futures_klines`，新增 `start_time_ms` 參數**

將原本：
```python
def get_futures_klines(
    self,
    symbol: str,
    interval: str = '1m',
    limit: int = 100,
) -> Optional[List]:
    return self.api.get_futures_klines(symbol=symbol, interval=interval, limit=limit)
```

改為：
```python
def get_futures_klines(
    self,
    symbol: str,
    interval: str = '1m',
    limit: int = 100,
    start_time_ms: Optional[int] = None,
) -> Optional[List]:
    """Fetch futures klines.

    Args:
        start_time_ms: Optional start time in epoch milliseconds.
                       Binance returns at most 1000 bars per request.
    """
    return self.api.get_futures_klines(
        symbol=symbol,
        interval=interval,
        limit=limit,
        startTime=start_time_ms,
    )
```

- [ ] **步驟 2：確認既有 warmup 呼叫（不傳 start_time_ms）仍正常**

```bash
grep -n "get_futures_klines" live_trading.py src/orchestrator/live_trading_orchestrator.py
```
預期：找到的呼叫均未傳 `start_time_ms`，因為是可選參數，向下相容。

- [ ] **步驟 3：提交**

```bash
git add src/trader/binance_trader.py
git commit -m "feat: add start_time_ms param to BinanceTrader.get_futures_klines for gap replay"
```

---

## 任務 5：Gap Replay 測試

**檔案：**
- 建立：`tests/strategies/test_gap_replay.py`

- [ ] **步驟 1：撰寫測試**

```python
# tests/strategies/test_gap_replay.py
from datetime import datetime, timezone, timedelta
from src.strategies.dynamic_breakout_atx import DynamicBreakoutTrader
from src.strategies.strategy_state import DynamicBreakoutState

START = datetime(2026, 3, 18, tzinfo=timezone.utc)
INTERRUPTED = datetime(2026, 3, 19, 14, 0, tzinfo=timezone.utc)
LOOKBACK = 14


def _make_gap_bars(n: int, base_price: float = 86000.0) -> list:
    """模擬 Binance klines 格式（index 4=close, 5=volume, 6=close_time_ms）。"""
    bars = []
    for i in range(n):
        ts_ms = int((INTERRUPTED + timedelta(minutes=i)).timestamp() * 1000)
        bars.append([0, 0, 0, 0, base_price + i, 100.0 + i, ts_ms, 0, 0, 0, 0, 0])
    return bars


def _make_saved_state(high: float = 85000.0) -> DynamicBreakoutState:
    return DynamicBreakoutState(
        symbol="BTCUSDT",
        start_time=START,
        interrupted_at=INTERRUPTED,
        mean_atr=12.5, mean_vol=340.0, mean_adx=18.0,
        high=high, low=82000.0, short_high=84500.0, short_low=83000.0,
        prices=[83000.0] * LOOKBACK,
        volumes=[100.0] * LOOKBACK,
        atr_values=[12.0] * LOOKBACK,
        adx_values=[18.0] * LOOKBACK,
        num_trade=0, total_earn=0.0,
    )


def test_gap_replay_suppresses_signals():
    """gap replay（warmup_with_history）期間不應觸發任何 on_signal。"""
    signals = []
    trader = DynamicBreakoutTrader(
        symbol="BTCUSDT", start_time=START,
        on_signal=lambda s: signals.append(s)
    )
    trader.restore_state(_make_saved_state())
    trader.warmup_with_history(_make_gap_bars(30))
    assert signals == []


def test_gap_replay_updates_rolling_high():
    """gap replay 後，rolling high 應反映新的更高價格（舊資料被 deque 淘汰）。"""
    trader = DynamicBreakoutTrader(symbol="BTCUSDT", lookback=LOOKBACK, start_time=START)
    trader.restore_state(_make_saved_state(high=85000.0))

    # 餵入 LOOKBACK 根以上的 gap bars，舊資料（83000）完全淘汰
    # 新價格從 86000 起跳，rolling high 必須 > 85000
    trader.warmup_with_history(_make_gap_bars(LOOKBACK + 5, base_price=86000.0))
    assert trader.high > 85000.0
```

- [ ] **步驟 2：執行測試確認通過**

```bash
pytest tests/strategies/test_gap_replay.py -v
```
預期：2 tests PASS（僅用已實作的 restore_state + warmup_with_history）

- [ ] **步驟 3：提交**

```bash
git add tests/strategies/test_gap_replay.py
git commit -m "test: add gap replay signal suppression and indicator update tests"
```

---

## 任務 6：整合 live_trading.py + Config

**檔案：**
- 修改：`src/config/trading_config.py`
- 修改：`live_trading.py`
- 修改：`.env.template`

> **注意：** 每 tick 存狀態每分鐘約 100+ 次寫入（100 symbol），屬可接受的 I/O
> 量（每筆 < 2KB，total < 200KB/min）。若未來 symbol 數量大幅增長，可在此
> task 中評估每 N tick 存一次。目前保持每 tick 存以最大化恢復精度。

- [ ] **步驟 1：在 `LiveTradingConfig` 新增 `state_dir` 欄位**

在 `src/config/trading_config.py` 找到 `LiveTradingConfig`，新增：
```python
state_dir: str = Field(default="state", description="Per-symbol strategy state directory")
```

- [ ] **步驟 2：在 `load_config_from_env` 補上 `state_dir` 的讀取**

在 `load_config_from_env()` 的 `LiveTradingConfig(...)` 建構中（約 line 159）加入：
```python
state_dir=os.getenv('STATE_DIR', 'state'),
```

- [ ] **步驟 3：在 `.env.template` 新增**

```
STATE_DIR=state
```

- [ ] **步驟 4：修改 `live_trading.py` — 初始化 StateManager + 回復邏輯**

在現有 import 區加入：
```python
from datetime import timezone
from src.state.state_manager import StrategyStateManager
```

在 `run_live_trading` 函式初始化段（BinanceTrader 建立後）加入：
```python
state_manager = StrategyStateManager(state_dir=config.state_dir)
```

找到建立 strategy + warmup 的段落，將原本：
```python
strategy = DynamicBreakoutTrader(symbol=symbol, ..., on_signal=None)
strategy.warmup_with_history(bars)
strategy.on_signal = handle_signal
```

改為：
```python
strategy = DynamicBreakoutTrader(
    symbol=symbol, ...,
    start_time=datetime.now(tz=timezone.utc),
    on_signal=None
)

saved_state = state_manager.load(symbol)
if saved_state:
    strategy.restore_state(saved_state)
    logger.info("[%s] State restored from %s, fetching gap klines...",
                symbol, saved_state.interrupted_at)
    interrupted_ms = int(saved_state.interrupted_at.timestamp() * 1000)
    gap_bars = trader.get_futures_klines(
        symbol, interval="1m",
        limit=1000,
        start_time_ms=interrupted_ms,
    )
    if gap_bars:
        if len(gap_bars) >= 1000:
            logger.warning("[%s] Gap replay hit 1000-bar API limit; "
                           "indicators may not reflect full gap.", symbol)
        strategy.warmup_with_history(gap_bars)
        logger.info("[%s] Gap replay done (%d bars)", symbol, len(gap_bars))
else:
    strategy.warmup_with_history(bars)

strategy.on_signal = handle_signal
```

- [ ] **步驟 5：在 `on_tick` 後加入每 tick 儲存**

找到 Kafka 消費迴圈中呼叫 `strategy.on_tick(ts, tick)` 之後，加入：
```python
state_manager.save(strategy.get_state())
```

- [ ] **步驟 6：手動整合驗證（啟動後觀察 log）**

```
[BTCUSDT] State restored from 2026-03-19T14:30:00+00:00, fetching gap klines...
[BTCUSDT] Gap replay done (47 bars)
```

重啟後確認 `state/BTCUSDT.json` 的 `interrupted_at` 已更新至最新 tick 時間。

- [ ] **步驟 7：提交**

```bash
git add live_trading.py src/config/trading_config.py .env.template
git commit -m "feat: integrate StrategyStateManager — restore + gap replay + per-tick save (S-1)"
```

---

## 全部測試驗收

```bash
pytest tests/strategies/test_strategy_state.py \
       tests/strategies/test_dynamic_breakout_state.py \
       tests/strategies/test_gap_replay.py \
       tests/state/test_state_manager.py \
       -v
```
預期：全部 PASS

```bash
pytest tests/ -v
```
預期：所有既有測試仍 PASS

---

## 驗收標準

| 項目 | 驗證方式 |
|------|---------|
| 所有新測試通過 | 上方 pytest 指令 |
| 既有測試不受影響 | `pytest tests/ -v` |
| 重啟後狀態回復 | log：`State restored from ...`、`Gap replay done` |
| gap replay 無信號 | log：replay 期間無 BUY/SELL 訊號 |
| 狀態檔 atomic write | `state/BTCUSDT.json` 不出現損壞（正常重啟測試） |
| gap > 1000 bars 有警告 | 停機 17h 以上重啟後 log 出現 `hit 1000-bar API limit` |
