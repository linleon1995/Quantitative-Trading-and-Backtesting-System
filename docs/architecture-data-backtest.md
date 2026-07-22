# 架構討論：資料收集、回測、線上交易的模組拆分

> 記錄日期：2026-03-21
> 討論背景：現有一個 live trading consumer，希望新增資料收集與回測能力，梳理三者的職責邊界與衝突解法。

---

## 問題描述

### 現狀
- `live_trading.py`：單一消費者，消費 Kafka → 觸發策略 → 送出真實訂單
- 無離線資料收集，無獨立回測模組

### 希望達到的目標
1. 獨立收集市場資料（K 線）供回測使用
2. 保存交易執行紀錄供事後分析
3. 完整的回測流程：填補空缺 → 執行策略模擬 → 輸出績效
4. 保持 live trading 不受干擾

---

## 核心衝突

### 衝突 1：即時資料 vs. 補空白資料

| 操作 | 來源 | 方向 | 寫入方式 |
|------|------|------|----------|
| 即時收集 | Kafka stream | 只往前（T+1, T+2...）| 連續 append |
| 補空白 | Binance REST API | 往回填（歷史區間）| batch insert |

兩者寫入同一個 storage，若同時執行可能發生：
- 重複寫入同一時間區間
- 寫入順序不一致造成 index 或查詢錯誤

**解法：啟動時序分離**
```
啟動
  └─► 偵測資料空缺（查 storage 最後一筆時間戳記）
        └─► 呼叫 REST API 補齊歷史到時間點 T
              └─► 標記「歷史完整到 T」
                    └─► 接上 Kafka，從 T+1 開始 append
```
歷史範圍（≤ T）與即時範圍（> T）不重疊，衝突消失。

### 衝突 2：回測需要完整資料，但收集可能中斷

- 系統重啟、網路斷線都會造成 Kafka 資料空缺
- 空缺資料下跑回測會導致指標計算錯誤（如 rolling high/low 斷層）

**解法：回測前強制檢查完整性**
```
啟動回測
  └─► 確認指定時間範圍內資料完整（無空缺）
        ├─► 有空缺 → 先補齊（呼叫 REST API）→ 再執行
        └─► 完整 → 直接執行回測
```

### 衝突 3：Live trading 與 online backtest 的執行環境混用

- 目前 `USE_TESTNET=True` 兼當「測試環境」，但 testnet 行為與 production 不完全相同
- Online backtest 的目的是驗證端到端流程（Kafka → 策略 → 下單），不是賺錢
- 需明確區分，避免測試流程意外影響真實帳戶

---

## 三模組設計

### Module 1：線上資料收集模組（Data Collector）

**職責：**
- 消費 Kafka K 線資料，持久化至本地 DB（SQLite / TimescaleDB / Parquet）
- 啟動時偵測並補齊歷史空缺（REST API gap-filler）
- 獨立執行，與 live trading 無直接依賴

**啟動流程：**
```
啟動
  └─► 查詢 storage，找出每個 symbol 最後一筆時間戳記
  └─► 呼叫 GET /fapi/v1/klines 補齊缺口（batch，最多 1000 根/次）
  └─► 空缺補完後，切換為 Kafka 即時消費模式
  └─► 每筆 K 線寫入 DB（symbol, interval, open_time, open, high, low, close, volume）
```

**附屬工具：gap-filler utility**
- 輸入：symbol、interval、start_time、end_time
- 輸出：填補指定時間範圍的歷史 K 線
- 可單獨呼叫，也可在模組啟動時自動觸發

**Storage schema（初步）：**
```sql
klines (
    symbol      TEXT,
    interval    TEXT,       -- '1m', '5m', ...
    open_time   INTEGER,    -- ms timestamp (primary key part)
    open        REAL,
    high        REAL,
    low         REAL,
    close       REAL,
    volume      REAL,
    PRIMARY KEY (symbol, interval, open_time)
)
```

---

### Module 2：回測模組（Backtest Engine）

**職責：**
- 從 DB 讀取指定時間範圍的 K 線資料
- 確認資料完整性（有空缺則呼叫 gap-filler）
- 以 `DynamicBreakoutTrader.on_tick()` 逐筆模擬
- 輸出：模擬交易紀錄、績效指標

**執行流程：**
```
指定（symbols, start_time, end_time, strategy_params）
  └─► 從 DB 讀取資料
  └─► 檢查完整性 → 有缺口則補齊
  └─► 初始化 strategy（warmup 用前 N 根）
  └─► 逐根 on_tick → 收集 BUY/SELL signals
  └─► 計算績效：勝率、最大回撤、Sharpe、avg holding time ...
  └─► 輸出報告（CSV / JSON / console）
```

**與 live trading 的關係：**
- 完全離線，不依賴 Kafka，不送真實訂單
- 共用 `DynamicBreakoutTrader` 策略核心（保持一致）
- 不依賴 live trading module，可獨立執行

---

### Module 3：線上回測模組（Online Backtest / Paper Trading）

**職責：**
- 驗證端到端流程：Kafka → 策略 → 下單邏輯
- 使用真實行情，但不送出真實訂單（paper trading 或 testnet）
- 主要用途：上線前的整合測試、新策略參數驗證

**與 live trading 的差異：**

| 項目 | Live Trading | Online Backtest |
|------|-------------|-----------------|
| 行情來源 | Kafka（真實） | Kafka（真實） |
| 下單目標 | 真實帳戶 | Paper（模擬成交）或 Testnet |
| 帳戶狀態 | 真實資金 | 虛擬資金 |
| 目的 | 賺錢 | 驗證流程正確性 |

**實作建議：**
- 透過 `TRADING_MODE=paper|testnet|production` 環境變數區分
- `PaperTrader` 實作 `BaseTrader` 介面，模擬成交而非送 API
- 與 live trading 共用 orchestrator，差異僅在 trader 實作

---

## 模組關係圖

```
Binance REST API
    │
    ▼
gap-filler utility ──────────────────────────────────┐
                                                      │ 補齊歷史空缺
Binance Futures WebSocket                             │
    │                                                 ▼
    ▼                                            Local DB (klines)
Kafka Producer                                        │
    │                                                 │
    ├──► Data Collector ──────────────────────────────┘
    │       (即時寫入)
    │
    ├──► Online Backtest Module (paper trading)
    │       共用 orchestrator + strategy
    │       差異：PaperTrader / TestnetTrader
    │
    └──► Live Trading Module (production)
            真實帳戶下單
            交易紀錄持久化 → Local DB (trade_records)

Local DB (klines + trade_records)
    │
    └──► Backtest Engine (離線)
            讀取歷史 K 線 → 模擬策略 → 輸出績效
```

---

## 交易紀錄的持久化（S-2 / S-2.1）

除了 K 線資料，每筆成交也需要持久化，供事後分析使用：

```sql
trade_records (
    id          INTEGER PRIMARY KEY,
    symbol      TEXT,
    direction   TEXT,       -- 'BUY' | 'SELL'
    entry_price REAL,
    exit_price  REAL,
    size        REAL,
    entry_time  INTEGER,    -- ms timestamp
    exit_time   INTEGER,
    holding_min REAL,
    gain_pct    REAL,
    fee         REAL,
    reason      TEXT,
    order_id    TEXT
)
```

這份資料可用於：
- 計算真實 total_earn（含手續費，對應 T-10 / T-11）
- 回測對照：模擬交易 vs. 真實交易的差異分析
- 策略調優：哪類市況勝率高、哪類容易被止損

---

## 待確認與後續決策

- [ ] Storage 技術選型：SQLite（輕量，單機）vs. TimescaleDB（時序查詢佳）vs. Parquet（離線分析佳）
- [ ] gap-filler 是獨立 script 還是整合進 Data Collector 啟動流程
- [ ] `TRADING_MODE` 環境變數設計：paper / testnet / production 三種
- [ ] Online Backtest 的虛擬資金初始值與帳戶狀態管理
- [ ] 回測報告格式（CLI 輸出 / JSON file / HTML report）
