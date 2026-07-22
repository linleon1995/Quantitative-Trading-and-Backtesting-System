# data-reconciliation 服務設計

> 建立日期：2026-07-23
> 對應 issue：#43
> 上游設計：[2026-07-23-multi-venue-k3s-architecture-design.md](2026-07-23-multi-venue-k3s-architecture-design.md) §6

## 1. 目的

把「啟動時補齊資料缺口」從 `DataCollector.startup_fill()` 內嵌邏輯，抽成一個**獨立、run-to-completion、可單獨部署（k8s Job / initContainer）**的元件。契約：

> 讀「上次寫入的最新一筆時間（checkpoint）」與「now」，補齊 `[checkpoint, now]` 缺口，**補完才放行 live 消費**，並回傳結構化報告供呼叫端判斷成敗。

## 2. Checkpoint 設計決策

**以 ArcticDB 中該 (symbol, interval) 最後一筆 kline 的 `open_time` 作為權威 checkpoint**（即「最新一筆寫入時間」），透過既有 `KlineStorage.get_last_timestamp()` 取得。

理由：最後持久化的那根 K 線的 open_time **就是**「最新一筆寫入時間」。另設一個 checkpoint store 會與實際資料兩份真相、可能漂移（寫了資料但 checkpoint 沒更新，或反之）。用資料本身當 checkpoint 無漂移、零額外狀態，符合 YAGNI。

> 未來若 ArcticDB 換後端（見上游 §9），此語意不變——只要 storage 能回報最後時間戳即可。

## 3. 元件與資料結構

### 3.1 `GapFiller.fill()` → 回傳 `FillResult`

現況 `fill()` 回傳 `None`。改為回傳結構化結果，讓上層能報告與驗證。既有行為（skip 門檻、分頁、fresh backfill）不變。

```python
@dataclass(frozen=True)
class FillResult:
    symbol: str
    interval: str
    last_ms: int | None     # checkpoint（None = 無既有資料）
    target_ms: int          # 補到哪（now 對齊到上一根收盤）
    rows_written: int
    skipped: bool           # gap 在門檻內，未打 API
    fresh: bool             # 無既有資料，做 default_lookback backfill
```

### 3.2 `DataReconciliation`

包裝 `GapFiller`，跨 symbol 執行並彙整報告。**逐 symbol 隔離失敗**：單一 symbol 拋錯不中斷整批，記為 `FAILED` 由報告反映。

```python
class ReconcileStatus(str, Enum):
    UP_TO_DATE = "up_to_date"             # gap 在門檻內，未補
    FILLED = "filled"                     # 補了既有資料後的缺口
    BACKFILLED_FRESH = "backfilled_fresh" # 無既有資料，default lookback 回補
    FAILED = "failed"                     # 補齊過程拋錯

@dataclass(frozen=True)
class ReconcileResult:
    symbol: str
    interval: str
    last_written_ms: int | None
    target_ms: int
    rows_written: int
    status: ReconcileStatus
    error: str | None = None

@dataclass(frozen=True)
class ReconcileReport:
    results: list[ReconcileResult]
    @property
    def ok(self) -> bool          # 無任何 FAILED
    @property
    def total_rows(self) -> int
    def failures(self) -> list[ReconcileResult]

class DataReconciliation:
    def __init__(self, gap_filler: GapFiller) -> None: ...
    def reconcile(self, symbol: str, interval: str) -> ReconcileResult: ...
    def reconcile_all(self, symbols, interval: str) -> ReconcileReport: ...
```

`FillResult` → `ReconcileStatus` 對應：`skipped=True` → `UP_TO_DATE`；`fresh=True` → `BACKFILLED_FRESH`；否則 → `FILLED`；`reconcile()` 內捕捉例外 → `FAILED`。

### 3.3 進入點 `data_reconciliation_main.py`

供 k8s Job / initContainer 使用（與 `data_collector_main.py` 同樣以環境變數設定）：組裝 `BinanceAPI` / `KlineStorage` / `GapFiller` / `DataReconciliation` → `reconcile_all` → log 報告 → `sys.exit(0 if report.ok else 1)`。exit code 是 Job/initContainer 判斷「補完才放行」的依據。

### 3.4 `DataCollector` 整合（live 前的 gate）

`DataCollector` 建構子參數 `gap_filler` → `reconciliation: DataReconciliation`。`startup_fill()` 委派 `reconciliation.reconcile_all(...)` 並回傳 `ReconcileReport`；`data_collector_main` 在 `run()` 前檢查報告。單一補缺口路徑，不再散落。

## 4. 資料流

```
啟動
  → DataReconciliation.reconcile_all(symbols, interval)
      for each symbol:
        last = storage.get_last_timestamp(symbol, interval)   # checkpoint
        GapFiller.fill → REST 分頁補 [last+interval, now)      # 補缺口
        → ReconcileResult(status)
  → ReconcileReport(ok?)
      ok  → 放行 live（DataCollector.run / 或 Job exit 0 讓主容器啟動）
      not → 記錄 failures，Job exit 1
```

## 5. 測試計畫

**`tests/test_gap_filler.py`（擴充）**
- 既有 4 個測試維持綠燈。
- 新增：`fill()` 回傳 `FillResult`，各欄位正確（filled / skipped / fresh 三種情境的 rows_written 與旗標）。

**`tests/test_data_reconciliation.py`（新增）**
- `reconcile` 回傳 `UP_TO_DATE`（gap_filler 回 skipped）。
- `reconcile` 回傳 `FILLED`（回 rows_written>0、非 fresh）。
- `reconcile` 回傳 `BACKFILLED_FRESH`（fresh=True）。
- `reconcile` 捕捉 `GapFiller.fill` 例外 → `FAILED` 且 error 有訊息，不外拋。
- `reconcile_all` 逐 symbol 隔離：一個 symbol 失敗，其餘照跑，`report.ok is False`，`failures()` 只含失敗者。
- `report.total_rows` 為各 result 加總；全成功時 `report.ok is True`。

**`tests/test_data_collector.py`（更新）**
- `startup_fill` 改為委派 `reconciliation.reconcile_all` 並回傳 report；更新既有 startup 測試。
- `_process_message` 相關測試不受影響。

**`tests/test_data_reconciliation_main.py`（新增，可選但納入）**
- report.ok → exit code 0；有 FAILED → exit code 1（以 monkeypatch 注入假 reconciliation）。

## 6. 範圍界線（YAGNI）

- 不引入獨立 checkpoint store（用 ArcticDB 最後時間戳）。
- 不做多 interval 同時校正（沿用單一 interval，跟現況一致）。
- 不處理 live 端訊號/OMS（那是後續服務）。
- 不改 ArcticDB 後端。
