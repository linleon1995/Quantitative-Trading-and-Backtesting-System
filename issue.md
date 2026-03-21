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
- S-2.1 [ ] 每筆成交後將交易明細（幣種、方向、入場/出場價、數量、報酬率、持倉時間、手續費等）持久化至 DB，供未來重新讀取、回測分析或策略調優使用
- S-3 [x] ~~log 分天保存（現有 log 過大）~~ **(fixed: live_trading.py, binanace_producer.py)**
    - 修正：`FileHandler` → `TimedRotatingFileHandler(when='midnight', utc=True)`，每日 UTC 午夜自動輪換
    - 輪換後的舊檔命名為 `live_trading.log.2026-03-05`，預設保留 30 天（`LOG_BACKUP_DAYS`）
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
- S-11 [x] ~~啟動時依 24h 交易量篩選幣種（`TRADING_MIN_24H_VOLUME_USDT`）~~ **(fixed: live_trading.py)**
    - 修正：啟動後呼叫 `GET /fapi/v1/ticker/24hr` 一次，將所有 `quoteVolume < min_24h_volume_usdt` 的 symbol 加入 `excluded_symbols` 排除清單
    - Kafka 消費迴圈中對排除清單的 symbol 直接 `continue`，不初始化 strategy 也不暖機
    - 預設 `TRADING_MIN_24H_VOLUME_USDT=0`（disabled），設為 `150000000` 即排除 150 M 以下

### 策略
- T-1 [ ] 為何會交易 USDCUSDT 這類標的（穩定幣不應列入交易） 因為你的策略符合，想辦法透過策略方式修正
- T-2 [ ] 買進條件：交易量突然上升，偏離標準
- T-3 [ ] 買進條件：過去呈現上漲趨勢（較長期，數小時以上）
- T-4 [ ] 買進條件：回撤不跌破上次近期低點
- T-5 [ ] Filter 條件（待定義）
- T-6 [ ] 固定比例持倉策略：每次買入固定比例（如 10%），所有幣種總持倉上限 100%，超過不追加
- T-7 [ ] 多幣種資金管理：不同幣種策略間的資金分配與互相影響需統一管控
- T-8 [ ] 指數追蹤與績效對比（以 BTC 或加權市場平均作為 benchmark）
- T-9 [ ] 買賣條件時間尺度不一致 → SELL 後立即重新 BUY（見 `trade_note.md`）
    - SELL 出場使用短期視窗（`short_high` / `short_low` drawback）判斷動能減弱
    - BUY 進場使用長期滾動高點（`dynamic_x = high - pr_x * mean_atr`，lookback=14）判斷趨勢維持
    - 兩者對「趨勢結束」的定義不一致：賣出後價格仍貼近 14 根高點 + 成交量仍偏高 → 立即再觸發買進
    - 唯一合理的例外是波動劇烈行情，其他情況皆屬策略設計問題
    - 候選修正：① SELL 後同 symbol 冷卻期 ② 統一趨勢判斷基準（ADX/EMA slope）③ 分離 entry/exit module

### 部署
- D-1 [ ] Producer `docker-compose` vs `docker run` 連線行為差異：`compose` 正常但 `docker run` 無法連上 Kafka，需分析 CMD / 網路設定
- D-2 [ ] Producer log 更新頻率：每 tick 都寫 log 過於頻繁，但完全不寫又難以追蹤，需設計合理頻率（如每分鐘彙整一次）
- D-3 [ ] WebSocket 斷線自動重連：處理 `ERROR - WebSocket error: received 1001 (going away)` 自動重試連線
- D-4 [ ] 補充 docker-compose 常用執行指令與啟動說明文件（script 或 README）
- D-5 [ ] 動態區分 localhost 與 Docker 環境的 Kafka broker endpoint（可先略過）
- D-6 [ ] Producer 啟動時 Kafka broker 尚未就緒導致 `NoBrokersAvailable` crash：`depends_on: kafka` 僅保證容器啟動順序，不保證 broker 已完全就緒；需透過 `docker-compose` `healthcheck` + `condition: service_healthy`（或 k8s readinessProbe + initContainer）確保 broker ready 後才啟動 producer，或在 producer 程式碼加入 retry with backoff 等待連線成功
    ```
    kafka.errors.NoBrokersAvailable: NoBrokersAvailable
    ```

### 架構
> Binance 交易所狀態是動態變化的，部分資訊不應只在 init 查詢一次，需有獨立線程持續監聽並即時更新本地狀態

- A-1 [ ] 槓桿限制動態監聽：各 symbol 支援的最大槓桿可能隨時調整（error `-2027`），不應只在 init 設定，需獨立線程定期查詢或監聽槓桿變更並同步更新，避免因槓桿超限導致下單失敗
- A-2 [ ] Symbol 上下架動態監聽：新幣上架與舊幣下架應由獨立線程監聽 Binance `exchangeInfo` 或推播事件，即時更新可交易 symbol 白名單，避免送單到已下架或已暫停的 symbol（error `-1121` / `-4140` 相關）
- A-3 [ ] 24h 交易量動態監聽：各 symbol 的 24h quoteVolume 是浮動的，不應只在 init 抓一次；應由獨立線程定期（如每小時）重新拉取並更新排除清單，避免原本量足的幣後來掉出門檻（或反之），不需在每根 K 線重複計算


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
    - `-2027` Exceeded the maximum allowable position at current leverage（倉位超過槓桿上限，與 B-4 
    ```
    The current symbol's leverage exceeds the maximum supported leverage of 5x. Please adjust to the maximum available leverage or modify it manually.
    ```
    官方直接不允許20倍槓桿，只允許5倍。這種交易可能是有高風險的，在init階段就應該被過濾掉。


- B-7 [ ] 時區不一致：timestamp 顯示與計算可能混用 UTC / local time，影響持倉時間計算與 log 對照

- B-8 [ ] `-1121 Invalid symbol` 未提前過濾：live trading 在送下單前未驗證 symbol 是否仍為有效的 Futures PERPETUAL 標的，導致對已下架或不存在的 symbol 送出訂單後才於 error handler 回報失敗，應在策略觸發信號時先對照有效 symbol 白名單（參見 A-2）過濾掉無效標的
    ```
    live_trading - INFO - Reason: Breakout: price 2.44 >= dynamic_x -2.70, volume 77 > mean 50
    API Error: 400, {'code': -1121, 'msg': 'Invalid symbol.'}
    live_trading - ERROR - [ICPUSDT] BUY ORDER FAILED: Invalid symbol. (code: -1121)
    ```

- B-9 [ ] `-4140 Invalid symbol status for opening position`：symbol 處於暫停交易狀態（非 `TRADING`），Binance 拒絕開倉；根因與 A-2 相同，需透過動態白名單提前過濾，短期可在 `_execute_buy` 前加一次 symbol status 查詢作為防護
    ```
    API Error: 400, {'code': -4140, 'msg': 'Invalid symbol status for opening position.'}
    live_trading - ERROR - [SOMIUSDT] BUY ORDER FAILED: Invalid symbol status for opening position. (code: -4140)
    ```

- B-10 [ ] `-2019 Margin is insufficient`：錯誤本身不是問題，可用保證金不足時 Binance 直接拒絕下單，行為正確；**根本問題在策略**：買入後倉位幾乎不動，動態增減極少，導致保證金長期被已有倉位佔用，後續新訊號觸發時自然無餘額可用；需改善策略的倉位周轉率與出場邏輯（參見 T-9），而非單純在下單前做保證金檢查
    ```
    live_trading - ERROR - BUY ORDER FAILED: Margin is insufficient. (code: -2019)
    ```