# 執行摘要（Executive Summary）

> 更新日期：2026-07-04
> 本文件是 2026-07-03 全專案盤點的濃縮版。細節見：
> [01 專案總覽](01-project-overview.md)｜[02 問題與解法](02-issues-and-solutions.md)｜[03 回測框架與服務拆分](03-backtest-framework-and-service-split.md)

## 專案一句話

Binance USDT 永續合約量化交易系統：WebSocket 行情 → Kafka → 策略（DynamicBreakout）→ 下單，另有 ArcticDB 資料層與簡易回測。

## 最重要的發現

🔴 **P-1：producer 與 live_trading 訊息格式斷裂（目前實盤收不到行情）**

`feature/data-infrastructure` 分支把 producer 改成新格式（只送收盤 K 線，欄位 `open_time`/`open`/`high`/`low`/`close`/`volume`），但 `live_trading.py:210` 仍讀舊欄位 `timestamp`（字串）、策略仍讀 `close_price`。兩者一起跑時每筆訊息都 KeyError 被丟棄。**修好 P-1 之前，其他一切免談。**

其他關鍵問題（詳見文件 02）：

| 編號 | 問題 |
|------|------|
| P-2 | 回測讀 Spot 舊資料庫，實盤交易 Futures — 回測結果無代表性 |
| P-3 | `backtest.py` 無資金模擬、無手續費、無組合層（wallet 建了沒用） |
| P-5 | 績效計算有三套互不一致的實作（evaluator / PortfolioTracker / 策略自記） |
| P-6 | 12 個測試失敗 + 大量遺留腳本 |
| P-7 | ArcticDB(LMDB) 多程序寫入風險 → 需「單一寫入者」原則 |
| B-4/B-6/B-8/B-9、A-1~A-3 | 下單前未過濾無效 symbol / 槓桿上限，共同解法是 exchange-info-monitor |

## 回測框架核心設計（文件 03 的 Part 1）

**一套核心、三種環境**：Strategy + Orchestrator + Accounting 只寫一份，環境差異隔離在兩個介面後：

- `DataFeed`：HistoricalFeed（ArcticDB）↔ KafkaFeed（即時）
- `Trader`：SimulatedTrader（成交模型 + 手續費 + 保證金）↔ BinanceTrader（testnet/真錢）
- `TRADING_MODE=backtest|paper|testnet|production` 切換；paper mode 幾乎免費附贈

技術要點：多 symbol 單一時間軸的事件驅動引擎（組合層資金管理的前提）、`SimulatedTrader` 實作既有 `BaseTrader` 介面、統一的 `Account`/`Metrics` 記帳模組（一次解掉 P-5、T-10、T-11、S-2、S-8/S-9）。

里程碑：M0 修 P-1 → M1 accounting → M2 SimulatedTrader → M3 HistoricalFeed → M4 引擎串接 → M5 報告落盤與舊件退役 → M6 paper mode。

## 服務拆分（文件 03 的 Part 2）

依**故障域與資料寫入權**拆，不依程式碼模組拆；monorepo + docker-compose，不做 microservice：

1. **market-data-producer**（現有）：WS → Kafka
2. **data-collector**（現有）：Kafka → ArcticDB，**唯一寫入者**
3. **exchange-info-monitor**（新增）：輪詢 exchangeInfo/槓桿/24h 量 → 白名單；先做成 trading-engine 內的 thread，穩定後再拆
4. **trading-engine**：策略+風控+下單+記帳，內部**不**再細拆
5. **notifier**：Telegram，初期併在 4 內
6. **backtest CLI**：批次工具，只讀不寫共享儲存

## 建議行動順序

1. **修 P-1**（統一 tick schema）— 半天內可完成，一切的前置
2. 完成 S-1（狀態回復，worktree 進行中）+ S-2（交易紀錄持久化）→ 達成「穩定跑一週」
3. exchange-info-monitor → 一次消掉 B-4/B-6/B-8/B-9 錯誤噪音
4. 回測框架 M1–M6（含 P-2 資料打通）
5. 清理遺留腳本與失敗測試（S-4、P-6）
6. 策略優化（T 系列）— 等回測可信之後
