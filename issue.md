## AI workflow

**Constitution**
- C-1 [ ] 當一個新功能涉及多個判斷跟多個轉換，若以集中且單一的實現完成，高機率這不是 root cause，或是架構有問題導致實現無法順利拆分到不同層級與模組；發生時需重新檢視設計與實現。

**待辦**
- W-1 [ ] 能夠取得 GitHub Issue 並且完成 issue 的內容
- W-2 [ ] 只要行為描述足夠完整，能夠自主驗證行為是否完成
- W-3 [ ] 要求讀取 log 來驗證行為是否完成，並且能夠分析 log 來找出問題所在
    - W-3.1 [ ] 要求 agent 盡可能在不同行為跟分支都描述成 log
- W-4 [ ] 整合 GitHub Issues
- W-5 [ ] 維護一個長期的 todos，以功能為單位紀錄（類似 GitHub + Spec Extraction 結果）
- W-6 [ ] 維護 Action and Results（timeline 形式，讓 AI 快速理解專案完成了什麼）
- W-7 [ ] 重新部署或是重新執行服務的能力，用於更新每次 AI 結果
- W-8 [ ] 接傳送/接收訊息的 API，可以手機下指令、查看更新結果
- W-9 [ ] 規格描述完整且多功能，可以讓 AI 工作時間更長、減少人為干預
- W-10 [ ] 後端優先開發：驗證可信度高、可自我驗證、可快速迭代；前端待後端穩定後再進行


## 產品功能
> **先改善系統並以能夠穩定執行策略至少一周為目標，再開始優化策略**

### 系統
- S-1 [ ] 能夠回復狀態（backtest & live trading 皆適用）
    - S-1.1 [ ] 透過 DB sync，live trading 優先注入最新交易紀錄
    - S-1.2 [ ] 交易的 queue data 也需同步 (strategy state, portfolio state)，確保回復後能夠繼續執行策略邏輯
- S-2 [ ] 能夠紀錄交易紀錄並分析（紀錄 API 所有可記錄的資料）
- S-3 [ ] log 分天保存（現有 log 過大）
- S-4 [ ] 移除非必要檔案，合併重複功能，簡化現有模組
- S-5 [ ] 區分 offline backtest、online backtest、production 三種環境，並能在三種環境中切換
- S-6 [x] ~~online backtest 每次重新開始時關閉所有 position，並 reset asset/account~~
- S-7 [ ] reset account 以確保每次測試初始條件一致
- S-8 [x] ~~績效 Summary 指標（S-8.1 + S-8.2 已實現）~~
    - S-8.1 [x] ~~遠端指標（每次 periodic_update 從交易所拉取）：Wallet Balance, Margin Balance, Unrealized PnL, Open PnL（各持倉）, 現有持倉數量~~
    - S-8.2 [x] ~~本地歷史指標（從 trade records 計算）：最大回撤、最大連續虧損、最大連續獲利、勝率、盈虧比（Profit Factor）、平均持倉時間~~

- S-9 [ ] 進階績效指標（未來考慮）
    - S-9.1 交易密度、手續費占比、資金利用率
    - S-9.2 風險指標：夏普比率、索提諾比率
- S-10 [ ] 新幣上架自動追蹤訂閱（Futures 上新的 PERPETUAL symbol 能自動加入 producer 訂閱）

### 策略
- T-1 [ ] 為何會交易 USDCUSDT 這類標的（穩定幣不應列入交易）
- T-2 [ ] 買進條件：交易量突然上升，偏離標準
- T-3 [ ] 買進條件：過去呈現上漲趨勢（較長期，數小時以上）
- T-4 [ ] 買進條件：回撤不跌破上次近期低點
- T-5 [ ] Filter 條件（待定義）
- T-6 [ ] 固定比例持倉策略：每次買入固定比例（如 10%），所有幣種總持倉上限 100%，超過不追加
- T-7 [ ] 多幣種資金管理：不同幣種策略間的資金分配與互相影響需統一管控
- T-8 [ ] 指數追蹤與績效對比（以 BTC 或加權市場平均作為 benchmark）

### 部署
- D-1 [ ] Producer `docker-compose` vs `docker run` 連線行為差異：`compose` 正常但 `docker run` 無法連上 Kafka，需分析 CMD / 網路設定
- D-2 [ ] Producer log 更新頻率：每 tick 都寫 log 過於頻繁，但完全不寫又難以追蹤，需設計合理頻率（如每分鐘彙整一次）
- D-3 [ ] WebSocket 斷線自動重連：處理 `ERROR - WebSocket error: received 1001 (going away)` 自動重試連線
- D-4 [ ] 補充 docker-compose 常用執行指令與啟動說明文件（script 或 README）
- D-5 [ ] 動態區分 localhost 與 Docker 環境的 Kafka broker endpoint（可先略過）


## Bug

### 已修復
- B-1 [x] ~~初始化錯誤導致在指標暖機前就觸發大量 BUY 信號~~ **(fixed: c482fb1)**
    - 根因：`self.high = float('-inf')` 但判斷用 `is None`，導致 `high` 永遠不更新，`dynamic_x = -inf`，所有 tick 都觸發 BUY
    - 修正：`self.high = None`，每 tick 更新 `max(prices)`；新增 `mean_atr is None or mean_vol is None` guard
    - 測試：`test_strategy_no_premature_signals()` 驗證暖機前 0 信號

- B-2 [x] ~~SELL 失敗：-4003 Quantity less than or equal to zero~~ **(fixed: binance_api.py)**
    - 根因：`create_futures_order` 未設 `newOrderRespType`，Binance Futures 預設回 **ACK** 模式
    - ACK 回應中 `executedQty="0"`, `avgPrice="0"` 為接受確認，非成交資料
    - 結果：`position['size'] = 0.0` 被存入本地 → SELL 送出 qty=0 → -4003
    - 修正：payload 加 `newOrderRespType: RESULT`，強制回傳最終成交資訊

- B-3 [x] ~~Spot-only symbol 送 Futures 下單 → -1121 Invalid symbol~~ **(fixed: binanace_producer.py)**
    - 根因：Producer 訂閱 Spot WebSocket (`stream.binance.com`) + Spot `exchangeInfo`，Consumer 送單到 Futures，symbol 不一致
    - 修正：Producer 改訂 Futures WebSocket (`fstream.binance.com`) + Futures `exchangeInfo`，只發送 `status=TRADING` + `contractType=PERPETUAL` 的 symbol

- B-5 [x] ~~初始交易參數計算錯誤：`dynamic_x` 需要時間累積，啟動時應撈歷史資料預熱；目前初始 `dynamic_x = 最新一筆收盤價`，等於必定觸發，導致倉位過多~~ **(fixed)**
    - 根因：新 symbol 首次出現時，strategy 從零初始化，`self.prices` 僅有 1 筆，rolling high ≈ 當前價，`dynamic_x ≈ current_price` → 立即觸發 BUY
    - 修正：新增 `DynamicBreakoutTrader.warmup_with_history(bars)` — 以歷史 klines 預熱指標，期間不發 signal；`live_trading.py` 建立 strategy 後立即呼叫，拉取 `(lookback + atr_period) × 3` 根歷史 K 線完成預熱，再掛上 `on_signal` handler
    - 測試：`test_strategy_warmup_with_history()` 驗證預熱期間 0 signal，預熱後指標就緒且 `dynamic_x < rolling_high`

### 未修復
- B-4 [ ] 槓桿錯誤，現在是 20 倍，不符合 config 的 1 倍設定

- B-6 [ ] 部分交易訊號不合理：
    - `-1022` Signature not valid（`币安人生USDT` 等含特殊字元的 symbol）
    - `-4140` Invalid symbol status for opening position（symbol 已下架或暫停）
    - `-2027` Exceeded the maximum allowable position at current leverage（倉位超過槓桿上限，與 B-4 相關）

- B-7 [ ] 時區不一致：timestamp 顯示與計算可能混用 UTC / local time，影響持倉時間計算與 log 對照