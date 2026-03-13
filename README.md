# message-services

The services for the message queue for the forum data

## FastAPI + GCP Pub/Sub API

這個專案提供一個使用 FastAPI 撰寫的 HTTP API，負責將論壇的 `post`、`comment`、`reaction` 的建立與更新事件，送到 GCP Pub/Sub 對應的 topic；同時提供 `POST /pubsub/push` 接收 Pub/Sub Push 訊息，並依事件內容呼叫 Keystone GraphQL 寫入資料。

### 安裝依賴

```bash
cd message-services
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 環境變數

請先確保 GCP 認證已經設定好（例如設定 `GOOGLE_APPLICATION_CREDENTIALS` 指向 service account json）。

再設定以下環境變數：

- `GCP_PROJECT_ID`: GCP 專案 ID（必填）
- `PUBSUB_TOPIC_POST` / `PUBSUB_TOPIC_COMMENT` / `PUBSUB_TOPIC_REACTION`: 各事件 topic 名稱
- `KEYSTONE_GQL_ENDPOINT`: Keystone GraphQL URL（Push 收到訊息時寫入用）
- `KEYSTONE_AUTH_TOKEN`: 選填，呼叫 Keystone 時帶入

### 啟動服務

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

啟動後可瀏覽：

- OpenAPI 文件：`http://localhost:8000/docs`
- 健康檢查：`http://localhost:8000/health`

### API 範例

#### 建立 Post 事件

`POST /post/create`

```json
{
  "id": "post-id-123",
  "title": "標題",
  "content_zh": "內文",
  "author_id": "member-id-1",
  "is_active": true
}
```

#### 更新 Comment 事件

`POST /comment/update`

```json
{
  "id": "comment-id-123",
  "post_id": "post-id-123",
  "member_id": "member-id-1",
  "content": "更新後的留言內容",
  "is_edited": true
}
```

#### 建立 Reaction 事件

`POST /reaction/create`

```json
{
  "id": "reaction-id-1",
  "member_id": "member-id-1",
  "post_id": "post-id-123",
  "emotion": "happy"
}
```

所有成功請求都會回傳對應 Pub/Sub `message_id`：

```json
{
  "message_id": "1234567890"
}
```

