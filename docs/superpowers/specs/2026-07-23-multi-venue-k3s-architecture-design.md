# 多來源交易系統架構設計（Multi-Venue / k3s）

> 建立日期：2026-07-23
> 狀態：設計定案（方案 B）
> 相關文件：[../../03-backtest-framework-and-service-split.md](../../03-backtest-framework-and-service-split.md)、[../../04-startup-orchestration-and-state-recovery.md](../../04-startup-orchestration-and-state-recovery.md)

## 1. 背景與目標

系統要從目前「Binance 單一來源」擴展到 **6 個異質來源**：2 個 DEX、2 個 CEX、1 個美股、1 個台股。基礎設施短期以 **Docker Compose** 落地，中長期遷移到 **k3s**。

核心設計問題：訊號產生與實際交易的 **pod 邊界**如何切。

## 2. 核心決策

### 2.1 三層分解

多來源交易系統天然分三層，每層的 pod 切分準則不同：

| 層 | 切分準則 | 理由 |
|---|---|---|
| **資料收集（connector）** | 按 venue（幾乎必分） | 協定、SDK、斷線重連、憑證、rate limit 全不同 |
| **訊號 / 策略** | 按 Kafka topic 訂閱（預設一策略×市場一 pod） | 邊界跟資料流走，不跟 pod 走；未來跨市場策略只是「多訂幾個 topic」 |
| **執行 / OMS** | 按 venue（方案 B） | 下單金鑰、rate limit、風控、對帳、失敗語意各自獨立 |

### 2.2 pod 邊界判準

「切成獨立 pod」才買得到、同一 process 內 module/thread 買不到的能力：故障域、資源配額/排程、獨立擴縮、部署節奏、憑證最小化、異質依賴、重啟/對帳語意。

**判準：這兩個東西需不需要「各自獨立地」失敗 / 擴縮 / 部署 / 授權 / 排程？任一維答「要」就切；全「不用」就合。** 與「有幾個市場」無關。

### 2.3 訊號 / 執行邊界：選定方案 B

策略只發訊號到 `signal.*` topic；每個 venue 一個 OMS 消費、風控、下單、對帳。

| 維度 | A 同pod | **B venue-OMS** | C 全域OMS | D 每策略OMS |
|---|---|---|---|---|
| 延遲 | 最低 | +1 hop | +1 hop | +1 hop |
| 下單金鑰安全域 | 散(差) | **每venue收斂** | 集中一點 | 散(差) |
| 改策略是否碰下單 | 碰 | **不碰** | 不碰 | 不碰 |
| venue 間故障隔離 | 無 | **有** | 無 | 有 |
| 同venue多策略淨額 | 不行 | **統一** | 統一 | 各打各(打架) |
| 全域曝險控制 | 難 | 需另加 gateway | 內建最易 | 難 |
| shadow / 快速上下架 | 難 | **易** | 易 | 中 |

**成本效益**：B 花成本買隔離，C 花風險換全域視角。B 的成本現在就值得付（隔離是結構性的）；C 的效益（全域曝險）只有在「≥2 venue 同時用共享資金」時才出現。路徑：**先上 B；需要全域曝險時，在 B 之上加一個薄的 portfolio-risk gateway**（訊號先過全域風控閘再分派各 venue OMS），用 B 的隔離拿到 C 的視角，需要時才付 C 的成本。

**術語**：*venue* = 在哪下單（Binance/Uniswap/券商，各有一套 API/憑證/rate limit/撮合規則）。*OMS* = 誰來下單並管好單一生（接單、風控、下單改單撤單、成交回報、對帳、記帳）。對照現有程式：`orchestrator/`（風控/記帳/對帳）+ `trader/`（呼叫 API）合起來 = 一個 venue 的 OMS。

## 3. 服務清單

| 服務 | 職責 | 狀態 | 副本模型 |
|---|---|---|---|
| **data-collector** | 每來源一 pod，訂 WS、正規化 → Kafka；寫 ArcticDB 並更新 `last_written_time` checkpoint | 幾乎無狀態 | 每來源 1 |
| **data-reconciliation** | 啟動時讀 checkpoint 與 now，補 `[last_written_time, now]` 缺口到 ArcticDB，補完才放行 | run-to-completion | 每來源 1（啟動時） |
| **strategy** | 消費行情 topic，算訊號 → `signal.*`；單策略×單市場一 pod | 無狀態（指標狀態外置） | 策略數 × 市場數 |
| **oms** | 每 venue 一 pod，消費 `signal.*`、風控/淨額、下單、對帳、記帳 | 有狀態（部位/掛單） | 每 venue 1 |
| **trade-state-store** | 交易狀態（部位、掛單、策略指標狀態）持久化 | 有狀態 | 1（或 managed） |
| Kafka / ArcticDB | 訊息匯流 / 行情儲存 | 有狀態 | — |

## 4. 服務偶合關係

```mermaid
flowchart LR
  subgraph SRC[來源]
    B[Binance CEX]
    U[Uniswap DEX]
  end

  subgraph COL[data-collector 每來源一 pod]
    C1[collector-binance]
    C2[collector-uniswap]
  end

  K[(Kafka)]
  A[(ArcticDB 行情)]
  CP[[checkpoint: last_written_time]]

  subgraph REC[data-reconciliation 啟動時]
    R[gap-filler init/Job]
  end

  subgraph STR[strategy 策略×市場]
    S1[momentum@binance]
    S2[momentum@uniswap]
  end

  subgraph OMS[OMS 每 venue]
    O1[oms-binance]
    O2[oms-uniswap]
  end

  ST[(trade-state-store)]

  B --> C1
  U --> C2
  C1 --> K
  C2 --> K
  C1 --> A
  C2 --> A
  C1 -. 更新 .-> CP
  C2 -. 更新 .-> CP

  R -. 讀 last_written_time .-> CP
  R -->|REST 補缺口| A

  K -->|行情| S1
  K -->|行情| S2
  S1 -->|signal.*| K
  S2 -->|signal.*| K
  K -->|signal.binance| O1
  K -->|signal.uniswap| O2

  O1 <-->|下單/查詢| B
  O2 <-->|下單/查詢| U
  O1 <-->|部位/掛單| ST
  O2 <-->|部位/掛單| ST
  S1 <-.指標狀態.-> ST
  S2 <-.指標狀態.-> ST
```

## 5. Docker Compose ↔ k3s 元件對照

### 通用概念

| 概念 | Docker Compose | k3s |
|---|---|---|
| 長駐服務 | `service` | Deployment（無狀態）/ StatefulSet（有狀態） |
| 多副本 | `deploy.replicas` / `scale` | Deployment replicas + HPA |
| 一次性/啟動任務 | 前置 container + `depends_on` | initContainer 或 Job |
| 定時任務 | cron container | CronJob |
| 服務發現 | compose network + service 名 | Service (ClusterIP) + DNS |
| 設定 | `environment` / `env_file` | ConfigMap |
| 機密 | `.env` | Secret（進階：sealed-secrets/Vault） |
| 持久卷 | named `volumes` | PVC + StorageClass（k3s 內建 local-path） |
| 對外 | `ports` | Service(NodePort/LB) / Ingress |
| 資源限制 | `deploy.resources` | resources.requests/limits |
| 健康檢查 | `healthcheck` | liveness / readiness probe |
| 啟動順序 | `depends_on` | initContainer + probe（語意不同，要重寫） |

### 各服務

| 服務 | Compose | k3s | 為什麼 |
|---|---|---|---|
| data-collector | 每來源一 service | Deployment / 來源 | 長駐、可獨立擴縮 |
| data-reconciliation | 前置 one-shot container | initContainer 或 Job | run-to-completion |
| strategy | 每(策略×市場)一 service | Deployment | 無狀態，可隨時被殺 |
| oms | 每 venue 一 service | StatefulSet / venue | 需穩定身分做對帳、冪等 |
| trade-state-store | postgres + volume | StatefulSet + PVC 或 managed | 有狀態 |
| Kafka | service + volume | StatefulSet + PVC（prod 用 Strimzi） | 有狀態 |
| ArcticDB | named volume | PVC（單 writer） | lmdb 檔案 |

## 6. 資料 / 交易狀態恢復

兩者同一模式：**checkpoint + 啟動時只 replay/對帳「差異」**，不是全量重算。

**資料恢復（reconciliation）**
1. collector 每寫一筆 kline → 更新 `last_written_time`(per symbol/interval)。
2. 啟動 → reconciliation 讀 `last_written_time` 與 `now` → 缺口 `[last_written_time, now]` 用 REST 分頁補齊（現有 GapFiller）→ 寫回 ArcticDB。
3. 補完才放行 live。Compose：collector entrypoint 前置步驟；k3s：initContainer。

**交易狀態恢復（StartupCoordinator）**
1. OMS 啟動 → 從 trade-state-store 讀上次持久化的部位/掛單/策略指標狀態。
2. 呼叫 venue REST 查實際部位與未成交單。
3. 對帳差異（現有 StartupCoordinator / StateAligner）→ 對齊後才吃 `signal.*`。
4. 策略指標 warmup 狀態從 store 載回或 `warmup_with_history` 重建。

> 缺口只需：把 JSON 狀態檔升級成正式 trade-state-store，並把 reconciliation 做成明確的啟動階段。核心邏輯已存在。

## 7. Compose 階段限制

| 限制 | 具體故障場景 | k8s 怎麼補 |
|---|---|---|
| **單機、無 HA** | 硬碟/斷電/panic → collector、strategy、OMS、Kafka、DB 全同時消失 | 多節點；node 掛 → pod 自動重排到其他 node |
| **無自動擴縮** | 某市場爆量要人工 `scale` | HPA 依 CPU/lag 自動增減副本 |
| **無自癒** | process 沒死但卡住（deadlock/洩漏），Compose 看不出來，策略默默停擺 | liveness probe 戳不通就殺重建；readiness 擋未就緒流量 |
| **Kafka 單 broker** | replication factor 1，broker 磁碟壞 → 未消費訊息永久消失（含 `signal.*`） | Strimzi 多 broker，RF≥3 不丟 |
| **ArcticDB 單 writer** | lmdb 本質：多 writer 撞鎖/損毀；寫入無法擴 | **上 k8s 也不會消失**，見 §9 升級選項 |
| **Secret 弱** | API key 明文躺磁碟，易被 dump / 誤 commit | Secret + RBAC，每 venue key 只給對應 OMS |
| **排程土法** | 定時對帳靠 crontab container，失敗很安靜 | CronJob 一級公民，有歷史/重試 |
| **資源隔離弱** | 某服務洩漏 → host OOM killer 可能殺到無辜的 OMS/Kafka | pod limits，超標只殺自己 |

## 8. 過渡 k8s 成本

- 營運學習：叢集運維、YAML/Helm/Kustomize、監控（Prometheus/Grafana）、log 聚合（Loki）。
- 有狀態服務最痛：Kafka（Strimzi）、ArcticDB（PVC + 單 writer 或換後端）、DB（StatefulSet 或 managed）。
- 啟動依賴重寫：`depends_on` → initContainer/probe/Job。
- 服務被隨時殺：所有服務要能被殺 + 冪等重啟（reconcile 機制剛好滿足）。
- 網路/儲存模型：Service DNS、NetworkPolicy、Ingress；StorageClass（local-path 綁節點，多節點要換 provisioner）。
- CI/CD：build image → registry → GitOps（ArgoCD/Flux）。

## 9. ArcticDB 升級選項

lmdb 後端的「單 writer + 單機檔案」是本質限制。升級選項：

| 選項 | 作法 | 優 | 缺 |
|---|---|---|---|
| **A. ArcticDB + S3/MinIO** ✅ | 把 URI 從 `lmdb://` 改成 `s3://`（自建 MinIO StatefulSet 或雲 S3） | **保留全部 ArcticDB 程式（KlineStorage）**，只改連線字串；解除單 writer；儲存可 HA | 多一個 MinIO 服務要顧 |
| B. 換 TimescaleDB | Postgres 時序擴充；與 trade-state-store 同一 Postgres 技術棧 | 少一種技術；SQL 生態成熟 | 要重寫儲存層（KlineStorage） |
| C. 換 ClickHouse/QuestDB | 專用時序 OLAP | 大量歷史回測查詢最快 | 新技術棧、新運維 |
| D. 維持 lmdb | StatefulSet 固定單 writer pod | 零改動 | 限制不解除，寫入不可擴 |

**建議**：短期維持 lmdb（選項 D）；要解除單 writer 時走 **選項 A（ArcticDB + MinIO/S3）**，因為 `KlineStorage` 程式零改動、只換 URI，是遷移成本最低的升級。若日後要跟 trade-state-store 收斂技術棧再評估 B。

## 10. REPO / 部署管理

Monorepo，程式與部署分層，image 為 compose/k8s 共同貨幣：

```
repo/
  src/                     # 共用：算子、trader、orchestrator、strategies
  services/                # 各 service entrypoint + Dockerfile
    data-collector/ reconciliation/ strategy/ oms/
  deploy/
    compose/               # docker-compose.yml + override.dev/prod.yml
    k8s/
      base/                # kustomize base
      overlays/{dev,prod}/ # 只覆蓋差異（副本、resources、HPA）
  .github/workflows/       # CI: test → build → push
```

原則：①一份程式碼多 entrypoint，共用 `src` 打 base image（可分族 operator-base-crypto/equity）。②image 不變只換編排層，compose/k8s 用同一 git-sha tag。③base+overlay 避免 manifest 漂移。④config/secret 外置不進 image。⑤一策略=一份 values，新策略=複製 values+新 tag。⑥GitOps as truth。

## 11. 待釘死細節（實作前需定案）

- `signal.*` topic 命名與 schema（含 correlation-id 追蹤訊號→成交）。
- shadow→live 切換機制（建議做在 OMS 端的消費 flag，而非策略端）。
- trade-state-store 選型（PostgreSQL 為預設）。
- 資源配置基線（見 §12）。

## 12. 資源估算

（詳見對話回覆；本節為落地時填入實測值的骨架）

- Dev（Compose 單機，範例 2 collector + 4 strategy + 2 OMS + Kafka + Postgres + ArcticDB）：約 4–6 vCPU、6–10 GB RAM。
- HA（k3s，stateful 3 副本）：Kafka 3 broker + Postgres HA，stateful 層 footprint 約 2–3×。
