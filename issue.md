## AI workflow
- [ ] 能夠取得github issue並且完成issue的內容
- [ ] 只要行為描述足夠完整，能夠自主驗證行為是否完成


## 產品功能
- [ ] 能夠回復狀態，無論是在backtest or live trading.
    - [ ] live trading, backtest都透過DB sync，唯一區別在於live trading會有實際的交易紀錄，因此要優先注入最新交易紀錄
- [ ] 能夠紀錄交易紀錄，並且能夠分析交易紀錄。
    紀錄API所有能夠記錄的資料

## bug
- [ ] 槓桿錯誤，現在是20倍，不符合config的1倍設定
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