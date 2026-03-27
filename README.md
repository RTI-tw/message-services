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
- `GEMINI_API_KEY`: 選填；設定後可使用 `POST /translate`（Gemini 多語翻譯）
- `GEMINI_MODEL`: 選填，預設 `gemini-1.5-flash`
- `GCS_BUCKET`: 匯出 JSON 到 GCS 的預設 bucket（`/export/contents-to-gcs`、`/export/topic-posts-to-gcs` 共用）
- Cloud Run 若要使用 `POST /export/contents-to-gcs`，執行身分需有目標 bucket 寫入權限（例如 `roles/storage.objectAdmin` 或最小必要權限）。

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

#### Keystone hooks：翻譯後寫回 CMS

`POST /hooks/sync-translations`（需 `GEMINI_API_KEY`、`KEYSTONE_GQL_ENDPOINT`）

依 forum-cms `Post.ts` / `comment.ts` 的 `content`（原文）、`language`、各語系 `content_*` 欄位語意，呼叫 Gemini 後以 GraphQL `updatePost` / `updateComment` 更新 `language` 與 `content_zh`、`content_en`、`content_vi`、`content_th`、`content_id`（Keystone 6 GraphQL snake_case）。

並會同時估算 `spamScore`（0–1）寫回 Keystone 的 `spamScore` 欄位。

```json
{
  "type": "post",
  "id": "clxxxxxxxxxxxxxxxxxxxx"
}
```

選填 `source_text`：若提供則以此字串翻譯，否則會先 GQL 查詢該筆的 `content`。

若回傳 **503**，回應 body 會含 `detail.code`（例如 `gemini_config` = 未設 `GEMINI_API_KEY`，`keystone_config` = 未設 `KEYSTONE_GQL_ENDPOINT`，`graphql_error` = Keystone GQL 錯誤）。請在 Cloud Run 環境變數確認上述變數與 GCP 已啟用 **Generative Language API**。

#### 文章翻譯（Gemini）

`POST /translate`（需設定 `GEMINI_API_KEY`）

```json
{
  "text": "สวัสดีตอนเช้า คุณสบายดีไหม"
}
```

#### 匯出全部 contents 到 GCS

`POST /export/contents-to-gcs`（需設定 `KEYSTONE_GQL_ENDPOINT`，且 Cloud Run 服務帳號可寫 GCS）

```json
{
  "prefix": "exports/contents/dev",
  "page_size": 200,
  "id": "clxxxxxxxxxxxxxxxxxxxx"
}
```

- 有傳 `id`：只匯出該筆 content 成一個 JSON 檔
- 沒傳 `id`：匯出全部 contents（分頁）

回傳範例：

```json
{
  "bucket": "your-export-bucket",
  "prefix": "exports/contents/dev/20260326T041500Z",
  "total_exported": 123,
  "sample_paths": [
    "exports/contents/dev/20260326T041500Z/homepage-banner-clx...json"
  ]
}
```

#### 匯出每個 Topic 的最新/熱門/含投票貼文到 GCS（3 份 JSON）

`POST /export/topic-posts-to-gcs`

用途：給 scheduler 定時呼叫，預先產出頁面需要資料。會上傳三個檔案：

- `latest.json`：每個 topic 的最新 post（依建立時間降冪）
- `hot.json`：每個 topic 的熱門 post（留言數最多）
- `with-poll.json`：每個 topic 中有投票內容的 post（依建立時間降冪）

```json
{
  "prefix": "exports/topic-posts/dev",
  "per_topic_limit": 10,
  "post_state": "active",
  "scan_multiplier": 10
}
```

說明：

- `post_state=active` 會映射到 Keystone `Post.status=published`
- 每個 topic 會先抓 `per_topic_limit * scan_multiplier` 筆，再計算熱門與含投票

回傳範例：

```json
{
  "bucket": "your-export-bucket",
  "prefix": "exports/topic-posts/dev/20260326T052000Z",
  "files": [
    "exports/topic-posts/dev/20260326T052000Z/latest.json",
    "exports/topic-posts/dev/20260326T052000Z/hot.json",
    "exports/topic-posts/dev/20260326T052000Z/with-poll.json"
  ],
  "topics_count": 8,
  "per_topic_limit": 10,
  "post_state": "published"
}
```

`POST /translate` 回傳範例（鍵名與 Gemini 約定一致：`detect-lang`、`translation` 內含 `zh-tw`、`en`、`vi`、`th`、`id`）：

```json
{
  "detect-lang": "th",
  "translation": {
    "zh-tw": "…",
    "en": "…",
    "vi": "…",
    "th": "…",
    "id": "…"
  }
}
```

