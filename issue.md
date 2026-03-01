## AI workflow
- [ ] 能夠取得github issue並且完成issue的內容
- [ ] 只要行為描述足夠完整，能夠自主驗證行為是否完成
- [ ] 要求讀取log來驗證行為是否完成，並且能夠分析log來找出問題所在
- [ ] 整合GitHub Issues
- [ ] 我認為要考慮維護一個長期的todos，以功能為單位紀錄，這樣可以幫助我們追蹤整個專案的進度和未來的計劃。可以理解成Github以及Spec Extractioin結果
- [ ] 還有一個Action and Results。最好是一個timeline的形式，這與todos不同，目的在於透過語意快速讓AI理解這個專案完成了甚麼。


## 產品功能
###  系統
- [ ] 能夠回復狀態，無論是在backtest or live trading.
    - [ ] live trading, backtest都透過DB sync，唯一區別在於live trading會有實際的交易紀錄，因此要優先注入
        - [ ] 最新交易紀錄
        - [ ] 交易的queue data
- [ ] 能夠紀錄交易紀錄，並且能夠分析交易紀錄。 (紀錄API所有能夠記錄的資料)
- [ ] log 分天保存  現有log過大
- [ ] 移除非必要檔案 以及 合併重複功能檔案 簡化現有模組
- [ ] 區分offline backtest 與 online backtest，以及production三種環境，並且能夠在三種環境中切換
- [x] online backtest由於UI限制，要求每次重新開始時關閉所有position，並reset asset或是account

###  策略
- ~~優先分析現有交易策略~~
    - ~~現在為甚麼不需要等14分鐘才能交易? 是因為有錯誤的初始假設?~~ **(resolved: c482fb1)**
        - 確認是初始化Bug：`self.high = float('-inf')` 導致 `dynamic_x = -inf`，任何價格 >= -inf 都觸發
        - 半小時268倉根本原因找到，已修正
    - [x] ~~看不出任何開倉的線型pattern，目前交易約半小時開了268倉~~ → Bug已修固，非策略問題
- **買進**
- [ ] 交易量的突然上升，偏離標準
- [ ] 過去呈現上漲趨勢 (較長期，數小時以上)
- [ ] 回撤不跌破上次近期低點
- **Filter**
-
###  部署
    

## bug
- [ ] 槓桿錯誤，現在是20倍，不符合config的1倍設定
- [x] ~~初始化錯誤導致在指標暖機前就觸發大量BUY信號~~ **(fixed: c482fb1)**
    - 根因: `self.high = float('-inf')` 但判斷用 `is None`，導致 `high` 永遠不更新，`dynamic_x = -inf`，所有tick都觸發BUY
    - 修正: `self.high = None`，每tick更新 `max(prices)`；新增 `mean_atr is None or mean_vol is None` guard
    - 測試: `test_strategy_no_premature_signals()` 驗證暖機前0信號
- [ ] 部分coin無法交易
    ```
    2026-03-02 00:52:08,981 - INFO - [币安人生USDT] Attempting BUY 1497 at market price ~0.07
    2026-03-02 00:52:08,981 - live_trading - INFO - [币安人生USDT] Attempting BUY 1497 at market price ~0.07
    2026-03-02 00:52:08,981 - INFO -   Reason: Breakout: price 0.07 >= dynamic_x -inf, volume 25861 > mean 3144
    2026-03-02 00:52:08,981 - live_trading - INFO -   Reason: Breakout: price 0.07 >= dynamic_x -inf, volume 25861 > mean 3144
    API Error: 400, {'code': -1022, 'msg': 'Signature for this request is not valid.'}
    2026-03-02 00:52:09,033 - ERROR - [币安人生USDT] BUY ORDER FAILED: Signature for this request is not valid. (code: -1022)
    2026-03-02 00:52:09,033 - live_trading - ERROR - [币安人生USDT] BUY ORDER FAILED: Signature for this request is not valid. (code: -1022)
    2026-03-02 00:52:09,033 - WARNING - Symbol FARMUSDT marked as invalid, skipping signal
    2026-03-02 00:52:09,033 - live_trading - WARNING - Symbol FARMUSDT marked as invalid, skipping signal
    2026-03-02 00:52:09,033 - INFO - [IDEXUSDT] Attempting BUY 15129 at market price ~0.01
    2026-03-02 00:52:09,033 - live_trading - INFO - [IDEXUSDT] Attempting BUY 15129 at market price ~0.01
    2026-03-02 00:52:09,033 - INFO -   Reason: Breakout: price 0.01 >= dynamic_x -inf, volume 1153 > mean 951
    2026-03-02 00:52:09,033 - live_trading - INFO -   Reason: Breakout: price 0.01 >= dynamic_x -inf, volume 1153 > mean 951
    API Error: 400, {'code': -4140, 'msg': 'Invalid symbol status for opening position.'}
    2026-03-02 00:52:09,088 - ERROR - [IDEXUSDT] BUY ORDER FAILED: Invalid symbol status for opening position. (code: -4140)
    2026-03-02 00:52:09,088 - live_trading - ERROR - [IDEXUSDT] BUY ORDER FAILED: Invalid symbol status for opening position. (code: -4140)
    ```