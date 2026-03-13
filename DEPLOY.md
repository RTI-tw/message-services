# 部署指南（GCP）

這份文件說明如何在 GCP 上建立 Pub/Sub topics、建置 image 並部署 API service（以 Cloud Run 為例）。

## 前置條件

- 已安裝並初始化 `gcloud` CLI
- 擁有一個 GCP 專案，且有足夠權限建立 Pub/Sub / Cloud Build / Cloud Run
- 已在本機或 CI 中登入：`gcloud auth login`、`gcloud config set project <PROJECT_ID>`

建議先設定環境變數：

```bash
export PROJECT_ID="你的專案 ID"
export REGION="asia-east1"              # 或你偏好的區域
export SERVICE_NAME="message-services"  # Cloud Run 服務名稱

export PUBSUB_TOPIC_POST="forum-post-events"
export PUBSUB_TOPIC_COMMENT="forum-comment-events"
export PUBSUB_TOPIC_REACTION="forum-reaction-events"
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

---

## Step 3. 使用 Cloud Build 建置並推送 image

在 repo 根目錄（`message-services/`）執行：

```bash
gcloud builds submit --config cloudbuild.yaml .
```

完成後會產生 image：

- `gcr.io/$PROJECT_ID/message-services`

---

## Step 4. 部署到 Cloud Run

以下以「公開 HTTP 服務」為例：

```bash
gcloud run deploy "${SERVICE_NAME}" \
  --image "gcr.io/${PROJECT_ID}/message-services" \
  --platform managed \
  --region "${REGION}" \
  --allow-unauthenticated \
  --port 8000 \
  --set-env-vars "GCP_PROJECT_ID=${PROJECT_ID},PUBSUB_TOPIC_POST=${PUBSUB_TOPIC_POST},PUBSUB_TOPIC_COMMENT=${PUBSUB_TOPIC_COMMENT},PUBSUB_TOPIC_REACTION=${PUBSUB_TOPIC_REACTION}"
```

部署成功後，Cloud Run 會回傳一個 URL，例如：

```text
https://message-services-xxxxxx-uc.a.run.app
```

你可以用這個 URL 呼叫：

- 健康檢查：`GET /health`
- 發佈事件：`POST /post/create`、`/post/update`、`/comment/create`、`/comment/update`、`/reaction/create`、`/reaction/update`

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

## Step 6. 部署 Subscriber（消費 Pub/Sub 訊息並寫入 Keystone）

Subscriber 也是用同一個 image，只是啟動指令不同（執行 `subscriber.main`）。

### 6.1 新增 subscriptions

如果你還沒有為三個 topic 建立 subscriptions，可以用下列指令：

```bash
gcloud pubsub subscriptions create "${PUBSUB_TOPIC_POST}-sub" \
  --topic "${PUBSUB_TOPIC_POST}"

gcloud pubsub subscriptions create "${PUBSUB_TOPIC_COMMENT}-sub" \
  --topic "${PUBSUB_TOPIC_COMMENT}"

gcloud pubsub subscriptions create "${PUBSUB_TOPIC_REACTION}-sub" \
  --topic "${PUBSUB_TOPIC_REACTION}"
```

然後設定環境變數：

```bash
export PUBSUB_SUB_POST="${PUBSUB_TOPIC_POST}-sub"
export PUBSUB_SUB_COMMENT="${PUBSUB_TOPIC_COMMENT}-sub"
export PUBSUB_SUB_REACTION="${PUBSUB_TOPIC_REACTION}-sub"
```

### 6.2 Keystone GraphQL 相關環境變數

```bash
export KEYSTONE_GQL_ENDPOINT="https://your-keystone-host/api/graphql"
export KEYSTONE_AUTH_TOKEN="your-token-if-needed"
```

> `KEYSTONE_AUTH_TOKEN` 如果不需要認證可以留空；若需要，subscriber 會自動在 HTTP Header 加上 `Authorization: Bearer <token>`。

### 6.3 以 Cloud Run 部署 Subscriber

可以用同一個 image，改成執行 subscriber：

```bash
gcloud run deploy "${SERVICE_NAME}-subscriber" \
  --image "gcr.io/${PROJECT_ID}/message-services" \
  --platform managed \
  --region "${REGION}" \
  --no-allow-unauthenticated \
  --port 8000 \
  --set-env-vars "GCP_PROJECT_ID=${PROJECT_ID},PUBSUB_SUB_POST=${PUBSUB_SUB_POST},PUBSUB_SUB_COMMENT=${PUBSUB_SUB_COMMENT},PUBSUB_SUB_REACTION=${PUBSUB_SUB_REACTION},KEYSTONE_GQL_ENDPOINT=${KEYSTONE_GQL_ENDPOINT},KEYSTONE_AUTH_TOKEN=${KEYSTONE_AUTH_TOKEN}" \
  --command "python" \
  --args "-m,subscriber.main"
```

> 這個 Cloud Run service 不需要對外暴露 HTTP，因此可以用 `--no-allow-unauthenticated`，純粹當成一個長時間執行的 subscriber worker。


