# message-services

The services for the message queue for the forum data

## FastAPI + GCP Pub/Sub API

這個專案提供一個使用 FastAPI 撰寫的 HTTP API，負責將論壇的 `post`、`comment`、`reaction`、`bookmark` 的建立與更新事件，送到 GCP Pub/Sub 對應的 topic；同時提供 `POST /pubsub/push` 接收 Pub/Sub Push 訊息，並依事件內容呼叫 Keystone GraphQL 寫入資料。

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
- `PUBSUB_TOPIC_POST` / `PUBSUB_TOPIC_COMMENT` / `PUBSUB_TOPIC_REACTION` / `PUBSUB_TOPIC_BOOKMARK`: 各事件 topic 名稱（bookmark 預設 `forum-bookmark-events`）
- `KEYSTONE_GQL_ENDPOINT`: Keystone GraphQL URL（Push 收到訊息時寫入用）
- `KEYSTONE_AUTH_TOKEN`: 選填，呼叫 Keystone 時帶入
- `GEMINI_API_KEY`: 選填；設定後可使用 `POST /translate`（Gemini 多語翻譯）
- `GEMINI_MODEL`: 選填，預設 `gemini-1.5-flash`

定時匯出 JSON 到 GCS 的 API 已移至 **`cron-services`** 專案（路徑與本 repo 同層），請改部署該服務並設定 `GCS_BUCKET` 等變數。

### 啟動服務

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

啟動後可瀏覽：

- OpenAPI 文件：`http://localhost:8000/docs`
- 健康檢查：`http://localhost:8000/health`

### 前端如何送 request 到 Publisher（寫入 Pub/Sub）

論壇前端或 BFF **不要**直接呼叫 GCP Pub/Sub API，而是對本服務的 HTTP API 送 **JSON body**。服務會驗證欄位、組成事件信封（`entity`、`operation`、`data`、`occurred_at`），再發佈到對應的 Pub/Sub topic。

- **URL**：部署後的 message-services 根網址（例如 `https://message-services-xxx.run.app`），**不要**結尾斜線。
- **標頭**：`Content-Type: application/json`
- **方法**：各資源皆為 `POST`，路徑見下表。
- **成功**：HTTP **202**，body 為 `{"message_id": "<Pub/Sub 訊息 id>"}`。
- **錯誤**：4xx（驗證失敗）、5xx（發佈失敗等）。
- **CORS**：本專案預設未啟用跨來源；若瀏覽器直連需自行加 CORS 或改由**同源 BFF**轉發。

| 意圖 | 路徑 |
|------|------|
| 建立貼文 | `POST /post/create` |
| 更新貼文 | `POST /post/update` |
| 建立留言 | `POST /comment/create` |
| 更新留言 | `POST /comment/update` |
| 建立反應 | `POST /reaction/create` |
| 更新反應 | `POST /reaction/update` |
| 建立書籤 | `POST /bookmark/create` |
| 更新書籤 | `POST /bookmark/update` |

#### `fetch` 範例（建立貼文，含投票內嵌）

```javascript
const BASE = 'https://your-message-services.example.com'; // 或本機 http://localhost:8000

async function publishPostCreate(payload) {
  const res = await fetch(`${BASE}/post/create`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  return res.json(); // { message_id: "..." }
}

// 最小必填：title。其餘欄位見 OpenAPI / app/schemas.py Post
await publishPostCreate({
  title: '標題',
  content: '原文內文',
  language: 'zh',
  author_id: 'member-keystone-id',
  topic_id: 'topic-keystone-id',
  ip: '203.0.113.10',
  status: 'published',
  poll: {
    title: '你喜歡哪個？',
    expires_at: '2026-12-31T15:00:00.000Z',
    options: [{ text: '選項甲' }, { text: '選項乙' }],
  },
});
```

#### `fetch` 範例（更新貼文）

更新時請帶 CMS 既有貼文 `id`；僅想改狀態時可只送 `id` + `title`（title 仍為 schema 必填）+ `status`（或舊版 `is_active`）。

```javascript
await fetch(`${BASE}/post/update`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    id: 'clxxxxxxxxxxxxxxxxxxxx',
    title: '標題',
    status: 'published',
    poll: {
      id: 'poll-keystone-id',
      title: '新投票標題',
      expires_at: '2027-01-01T00:00:00.000Z',
    },
  }),
});
```

#### `fetch` 範例（留言／反應）

```javascript
await fetch(`${BASE}/comment/create`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    member_id: 'member-id',
    post_id: 'post-id',
    content: '留言內容',
  }),
});

await fetch(`${BASE}/reaction/create`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    member_id: 'member-id',
    post_id: 'post-id',
    emotion: 'happy', // happy | angry | surprise | sad
  }),
});

await fetch(`${BASE}/bookmark/create`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    member_id: 'member-id',
    post_id: 'post-id',
  }),
});
```

#### 服務端實際發佈到 Pub/Sub 的 JSON 形狀（除錯用）

前端送出的物件會進入信封的 `data`；完整訊息大致為：

```json
{
  "entity": "post",
  "operation": "create",
  "data": { "title": "…", "content": "…", "poll": { "title": "…", "options": […] } },
  "occurred_at": "2026-03-28T12:00:00.000000"
}
```

欄位名以 **snake_case** 為主（如 `author_id`、`topic_id`、`spam_score`）；少數別名亦支援（例如 `spamScore`、`expiresAt`、`heroImageId`），與 Pydantic 模型一致。

### API 範例（精簡）

#### 建立 Post 事件

`POST /post/create`

```json
{
  "title": "標題",
  "content": "原文",
  "language": "zh",
  "author_id": "member-id-1",
  "topic_id": "topic-id-1",
  "ip": "203.0.113.1",
  "status": "published",
  "poll": {
    "title": "票選標題",
    "options": [{ "text": "A" }, { "text": "B" }]
  }
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

### 執行測試

```bash
pip install -r requirements-dev.txt
pytest
```

#### Keystone hooks：翻譯後寫回 CMS

`POST /hooks/sync-translations`（需 `GEMINI_API_KEY`、`KEYSTONE_GQL_ENDPOINT`）

依 forum-cms `Post.ts` / `comment.ts` 的原文欄位語意：

- `post`：翻譯 `title` 與 `content`，更新 `title_*` 與 `content_*`
- `comment`：翻譯 `content`，更新 `content_*`

並以 GraphQL `updatePost` / `updateComment` 同步更新 `language` 與各語系欄位（Keystone 6 GraphQL snake_case）。

並會同時估算 `spamScore`（0–1）寫回 Keystone 的 `spamScore` 欄位。

```json
{
  "type": "post",
  "id": "clxxxxxxxxxxxxxxxxxxxx"
}
```

選填 `source_text`：若提供則以此字串翻譯，否則會先 GQL 查詢該筆原文內容。
`post` 可另外傳 `source_title`（若省略會改由 GQL 讀取 title）。

若回傳 **503**，回應 body 會含 `detail.code`（例如 `gemini_config` = 未設 `GEMINI_API_KEY`，`keystone_config` = 未設 `KEYSTONE_GQL_ENDPOINT`，`graphql_error` = Keystone GQL 錯誤）。請在 Cloud Run 環境變數確認上述變數與 GCP 已啟用 **Generative Language API**。

#### 文章翻譯（Gemini）

`POST /translate`（需設定 `GEMINI_API_KEY`）

```json
{
  "text": "สวัสดีตอนเช้า คุณสบายดีไหม"
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

