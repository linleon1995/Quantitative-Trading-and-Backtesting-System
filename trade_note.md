# Trade Notes

> 用於記錄具體交易行為的觀察與分析，梳理策略邏輯問題，供策略調整參考。

---

## 觀察紀錄

### 2026-03-06 | MYXUSDT — 賣出異常 & 買進後未停損

#### 交易概要

| 訂單 ID | 方向 | 備註 |
|---------|------|------|
| 431365367 | SELL | 賣出時機可疑，疑似在趨勢中途被踢出 |
| 431403162 | BUY | 進場尚合理，但後續未在下跌行情中停損出場 |

#### 分析

**SELL 431365367 — 賣的怪怪的**
- 懷疑是 SELL WIN 條件觸發：`price < short_high * (1 - drawback)` 且 `holding_time > hold_minutes` 且 `price > entry`
- 問題：`short_high` 由非常短的視窗（`short_time_len` 根 K 線）決定，若盤中稍微拉高後回落就會觸發，而此時大趨勢可能仍在上行
- 本質是短期高點 drawback 與長期趨勢方向不一致；短視窗的局部高點容易在正常波動中被觸及，導致過早出場

**BUY 431403162 — 進場後沒閃掉崩跌**
- 進場條件觸發合理（`price >= dynamic_x` + 成交量surge），但後續發生急跌
- SELL LOSS 條件：`price < short_low * (1 - drawback)`，若短期低點本身就在下跌趨勢中持續刷新低，`short_low` 會不斷更新，`drawback` 相對基準也會下移，可能導致停損線追著跌而遲遲不出場
- 需確認：當時 `short_low` 的更新邏輯是否導致停損基準位置太低，或 `hold_minutes` 未到而停損條件未生效

#### 待確認
- [ ] 確認 431365367 SELL 的 reason（WIN 或 LOSS），查看當時 `short_high` vs 最終賣出價
- [ ] 確認 431403162 BUY 後的 K 線走勢及最終平倉時機，檢查 `short_low` 值變化
- [ ] 驗證 `short_high` / `short_low` 的視窗長度（`short_time_len`）是否合理，是否導致停利基準過敏感

---

## 策略行為問題

### 買賣條件時間尺度不一致 → 賣完馬上再買

#### 現象
某些幣種出現 SELL → BUY 極短間隔（同一 tick 或數根 K 線內）反覆進出場。

#### 根因分析

**BUY 使用長視窗判斷趨勢仍在**
```
dynamic_x = high - pr_x * mean_atr
```
- `high` = rolling lookback（預設 14 根）窗口的最高價
- 只要當前價格仍貼近 N 根 K 線的高點，就會觸發買進
- 這是 **長期（lookback）** 視角：認為趨勢維持

**SELL 使用短視窗判斷趨勢暫緩**
```
# WIN exit: 相對 short_high 回落
price < short_high * (1 - drawback)

# LOSS exit: 跌破 short_low drawback
price < short_low * (1 - drawback)
```
- `short_high` / `short_low` 由 `short_time_len` 決定（遠短於 lookback）
- 價格從短期高點小幅回落就觸發 SELL
- 這是 **短期（short_time_len）** 視角：認為動能減弱

**矛盾發生的路徑**
1. 短期動能稍微降溫 → SELL WIN 觸發，平倉
2. 賣出後價格仍貼近 14 根滾動高點 → `price >= dynamic_x` 仍成立
3. 成交量仍偏高 → BUY 再次觸發
4. 結果：在同一位置反覆進出，付出 2 次手續費，無實際獲利

#### 例外情況
- 波動劇烈的行情中（如爆量拉升後快速回調），此行為可能是合理的雙向操作
- 其餘情況皆應視為策略設計問題

#### 問題本質
| 邏輯層 | 時間尺度 | 判斷 |
|--------|----------|------|
| BUY `dynamic_x` | 長（lookback=14） | 趨勢維持，進場 |
| SELL WIN drawback | 短（short_time_len） | 動能減弱，出場 |

兩者使用不同的趨勢定義，缺乏一致的「趨勢結束」判斷基準。

#### 可能修正方向（待評估）
1. **SELL 後冷卻期**：出場後 N 分鐘（或 M 根 K 線）內不允許同一 symbol 再次買進
2. **統一趨勢判斷**：BUY 的入場條件加入「短期趨勢仍未終結」的確認，與 SELL 出場條件共用同一個趨勢指標（如 ADX / EMA slope）
3. **提高 BUY 門檻**：出場後若 `dynamic_x` 沒有明顯上移（代表沒有新的突破格局），則不重新進場
4. **分離 BUY/SELL 策略物件**：讓 entry module 與 exit module 各自維護其時間視窗並互相感知狀態，避免邏輯隱含衝突
