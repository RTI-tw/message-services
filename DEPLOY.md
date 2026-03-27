# 部署指南（GCP）

這份文件說明如何在 GCP 上建立 Pub/Sub topics、建置 image 並部署 API service（以 Cloud Run 為例）。

## 前置條件

- 已安裝並初始化 `gcloud` CLI
- 擁有一個 GCP 專案，且有足夠權限建立 Pub/Sub / Cloud Build / Cloud Run
- 已在本機或 CI 中登入：`gcloud auth login`、`gcloud config set project <PROJECT_ID>`
- 若要使用 `POST /export/contents-to-gcs`，Cloud Run 執行身分需有目標 bucket 的寫入權限（例如 `roles/storage.objectAdmin`）

建議先設定環境變數：

```bash
export PROJECT_ID="你的專案 ID"
export REGION="asia-east1"              # 或你偏好的區域
export SERVICE_NAME="message-services"   # Cloud Run 服務名稱

export PUBSUB_ENV="dev"                 # 環境名稱（例：dev / stg / prod）

# 若未顯式設定 PUBSUB_TOPIC_*，setup_pubsub.sh 會依 PUBSUB_ENV 自動組合名稱：
#   <PUBSUB_ENV>-forum-post-events / <PUBSUB_ENV>-forum-comment-events / ...
# 也可以自行指定完整 topic 名稱覆寫這些預設值：
# export PUBSUB_TOPIC_POST="dev-forum-post-events"
# export PUBSUB_TOPIC_COMMENT="dev-forum-comment-events"
# export PUBSUB_TOPIC_REACTION="dev-forum-reaction-events"

# 訂閱端改為 Push 時，部署完成後設成 Cloud Run URL + /pubsub/push
export PUBSUB_PUSH_ENDPOINT=""   # 例如 https://message-services-dev-xxx.asia-east1.run.app/pubsub/push
# 若要強制把已存在的 subscription 改成 Push，設為 1 後再執行 scripts/setup_pubsub.sh
export FORCE_PUSH=0

# Keystone hooks（POST /hooks/sync-translations）預設不需要 secret

# 匯出 JSON 到 GCS（/export/contents-to-gcs、/export/topic-posts-to-gcs 共用）
export GCS_BUCKET="your-export-bucket"
```

---

## Step 1. 啟用必要 API

```bash
gcloud services enable \
  pubsub.googleapis.com \
  cloudbuild.googleapis.com \
  run.googleapis.com
```

---

## Step 2. 建立 Pub/Sub Topics

### 手動建立（使用 gcloud）

```bash
gcloud pubsub topics create "${PUBSUB_TOPIC_POST}"
gcloud pubsub topics create "${PUBSUB_TOPIC_COMMENT}"
gcloud pubsub topics create "${PUBSUB_TOPIC_REACTION}"
```

### 一次建立（三個 topic）腳本

本 repo 中提供 `scripts/setup_pubsub.sh`：

```bash
chmod +x scripts/setup_pubsub.sh
./scripts/setup_pubsub.sh
```

腳本會：

- 檢查 `PROJECT_ID` 是否存在（從 `gcloud config get-value project` 取得）
- 建立上述三個 topics（若已存在會略過）
- 以及對應的三個 subscriptions（預設名稱為 `<topic>-sub`，可用環境變數 `PUBSUB_SUB_*` 覆寫）

---

## Step 3. 使用 Cloud Build 建置並推送 image

在 repo 根目錄（`message-services/`）執行：

```bash
gcloud builds submit --config cloudbuild.yaml .
```

完成後會產生 image：

- `gcr.io/$PROJECT_ID/message-services`

---

## Step 4. 部署到 Cloud Run（單一服務：API + Pub/Sub Push 訂閱端）

同一個服務同時提供：發佈事件的 API（publisher）與接收 Pub/Sub Push 的 endpoint（subscriber 邏輯）。需設定 Keystone GraphQL 相關變數，Push 收到訊息時才會寫入 Keystone。

```bash
gcloud run deploy "${SERVICE_NAME}" \
  --image "gcr.io/${PROJECT_ID}/message-services" \
  --platform managed \
  --region "${REGION}" \
  --allow-unauthenticated \
  --set-env-vars "GCP_PROJECT_ID=${PROJECT_ID},PUBSUB_TOPIC_POST=${PUBSUB_TOPIC_POST},PUBSUB_TOPIC_COMMENT=${PUBSUB_TOPIC_COMMENT},PUBSUB_TOPIC_REACTION=${PUBSUB_TOPIC_REACTION},KEYSTONE_GQL_ENDPOINT=${KEYSTONE_GQL_ENDPOINT},KEYSTONE_AUTH_TOKEN=${KEYSTONE_AUTH_TOKEN},GEMINI_API_KEY=${GEMINI_API_KEY},GEMINI_MODEL=${GEMINI_MODEL},GCS_BUCKET=${GCS_BUCKET}"
```

部署成功後，Cloud Run 會回傳一個 URL，例如：

```text
https://message-services-dev-xxxxxx.asia-east1.run.app
```

此 URL 可用於：

- 健康檢查：`GET /health`、`GET /healthz`
- 發佈事件：`POST /post/create`、`/post/update`、`/comment/create`、`/comment/update`、`/reaction/create`、`/reaction/update`
- Pub/Sub Push：`POST /pubsub/push`（由 GCP Pub/Sub 呼叫，不需手動打）

---

## Step 5. 測試 Pub/Sub 是否有收到訊息

你可以先建立一個暫時的 subscription 來觀察訊息：

```bash
gcloud pubsub subscriptions create test-post-sub \
  --topic "${PUBSUB_TOPIC_POST}"

gcloud pubsub subscriptions pull test-post-sub --auto-ack --limit 10
```

從 Cloud Run endpoint 打一個 `POST /post/create` 後，再用 `subscriptions pull` 應該可以看到對應的 JSON payload。

---

## Step 6. 使用 Pub/Sub Push 讓訊息寫入 Keystone

訂閱端改為 **Push**：Pub/Sub 會把訊息 POST 到同一個 Cloud Run 服務的 `/pubsub/push`，由該 endpoint 解碼並呼叫 Keystone GraphQL（與原本 subscriber 相同邏輯）。

### 6.1 Keystone 環境變數

部署 Step 4 時請一併設定（或事後在 Cloud Run 介面補上）：

```bash
export KEYSTONE_GQL_ENDPOINT="https://your-keystone-host/api/graphql"
export KEYSTONE_AUTH_TOKEN="your-token-if-needed"
```

> `KEYSTONE_AUTH_TOKEN` 若不需要認證可留空；需要時 Push handler 會帶 `Authorization: Bearer <token>` 呼叫 Keystone。

### 6.2 建立 Push subscriptions

**先完成 Step 4 部署**，取得 Cloud Run URL 後：

```bash
export PUBSUB_PUSH_ENDPOINT="https://你的服務URL/pubsub/push"
# 若已經存在 subscription 且想改成 Push，加上 FORCE_PUSH=1
export FORCE_PUSH=1
./scripts/setup_pubsub.sh
```

- 若 **尚未建立** 過 subscription：腳本會建立三個 **Push** subscription，並指向 `PUBSUB_PUSH_ENDPOINT`。
- 若 **已存在** subscription：
  - 預設（`FORCE_PUSH=0`）：略過，不變更現有設定
  - `FORCE_PUSH=1`：呼叫 `gcloud pubsub subscriptions update`，把 `push-endpoint` 更新為 `PUBSUB_PUSH_ENDPOINT`

之後當有事件發佈到 topic 時，Pub/Sub 會 POST 到 `https://你的服務URL/pubsub/push`，服務會解碼訊息並依 `entity`/`operation` 呼叫 Keystone 的 create/update mutation。


