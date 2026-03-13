#!/usr/bin/env bash

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"

if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "(unset)" ]]; then
  echo "ERROR: PROJECT_ID 未設定，請先執行："
  echo "  gcloud config set project <PROJECT_ID>"
  echo "或在環境中 export PROJECT_ID。"
  exit 1
fi

# 用 PUBSUB_ENV 來區分環境（例如 dev/stg/prod），只在未顯式指定 PUBSUB_TOPIC_* 時套用
PUBSUB_ENV="${PUBSUB_ENV:-}"

if [[ -n "${PUBSUB_ENV}" ]]; then
  PUBSUB_TOPIC_POST="${PUBSUB_TOPIC_POST:-${PUBSUB_ENV}-forum-post-events}"
  PUBSUB_TOPIC_COMMENT="${PUBSUB_TOPIC_COMMENT:-${PUBSUB_ENV}-forum-comment-events}"
  PUBSUB_TOPIC_REACTION="${PUBSUB_TOPIC_REACTION:-${PUBSUB_ENV}-forum-reaction-events}"
else
  PUBSUB_TOPIC_POST="${PUBSUB_TOPIC_POST:-forum-post-events}"
  PUBSUB_TOPIC_COMMENT="${PUBSUB_TOPIC_COMMENT:-forum-comment-events}"
  PUBSUB_TOPIC_REACTION="${PUBSUB_TOPIC_REACTION:-forum-reaction-events}"
fi

# 預設 subscription 名稱：<topic>-sub
PUBSUB_SUB_POST="${PUBSUB_SUB_POST:-${PUBSUB_TOPIC_POST}-sub}"
PUBSUB_SUB_COMMENT="${PUBSUB_SUB_COMMENT:-${PUBSUB_TOPIC_COMMENT}-sub}"
PUBSUB_SUB_REACTION="${PUBSUB_SUB_REACTION:-${PUBSUB_TOPIC_REACTION}-sub}"

# 若設定 PUBSUB_PUSH_ENDPOINT（例如 https://xxx.run.app/pubsub/push），則建立/更新為 Push subscription
PUBSUB_PUSH_ENDPOINT="${PUBSUB_PUSH_ENDPOINT:-}"
# 若 FORCE_PUSH=1，且 subscription 已存在，會自動執行 update 將 push-endpoint 更新為 PUBSUB_PUSH_ENDPOINT
FORCE_PUSH="${FORCE_PUSH:-0}"

echo "使用專案：${PROJECT_ID}"
if [[ -n "${PUBSUB_ENV}" ]]; then
  echo "環境：${PUBSUB_ENV}"
fi
echo "Post topic:     ${PUBSUB_TOPIC_POST} (sub: ${PUBSUB_SUB_POST})"
echo "Comment topic:  ${PUBSUB_TOPIC_COMMENT} (sub: ${PUBSUB_SUB_COMMENT})"
echo "Reaction topic: ${PUBSUB_TOPIC_REACTION} (sub: ${PUBSUB_SUB_REACTION})"
if [[ -n "${PUBSUB_PUSH_ENDPOINT}" ]]; then
  echo "Push endpoint:  ${PUBSUB_PUSH_ENDPOINT}"
fi
echo

create_topic_if_not_exists() {
  local topic="$1"
  if gcloud pubsub topics describe "${topic}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    echo "Topic '${topic}' 已存在，略過建立。"
  else
    echo "建立 topic '${topic}'..."
    gcloud pubsub topics create "${topic}" --project="${PROJECT_ID}"
  fi
}

create_topic_if_not_exists "${PUBSUB_TOPIC_POST}"
create_topic_if_not_exists "${PUBSUB_TOPIC_COMMENT}"
create_topic_if_not_exists "${PUBSUB_TOPIC_REACTION}"

echo

create_sub_if_not_exists() {
  local sub="$1"
  local topic="$2"
  if gcloud pubsub subscriptions describe "${sub}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    if [[ -n "${PUBSUB_PUSH_ENDPOINT}" && "${FORCE_PUSH}" == "1" ]]; then
      echo "Subscription '${sub}' 已存在，FORCE_PUSH=1，更新為 Push（endpoint: ${PUBSUB_PUSH_ENDPOINT}）..."
      gcloud pubsub subscriptions update "${sub}" \
        --push-endpoint="${PUBSUB_PUSH_ENDPOINT}" \
        --project="${PROJECT_ID}"
    else
      echo "Subscription '${sub}' 已存在，略過建立。"
    fi
  else
    echo "建立 subscription '${sub}' (topic: '${topic}')..."
    if [[ -n "${PUBSUB_PUSH_ENDPOINT}" ]]; then
      gcloud pubsub subscriptions create "${sub}" \
        --topic "${topic}" \
        --push-endpoint="${PUBSUB_PUSH_ENDPOINT}" \
        --project="${PROJECT_ID}"
    else
      gcloud pubsub subscriptions create "${sub}" \
        --topic "${topic}" \
        --project="${PROJECT_ID}"
    fi
  fi
}

create_sub_if_not_exists "${PUBSUB_SUB_POST}" "${PUBSUB_TOPIC_POST}"
create_sub_if_not_exists "${PUBSUB_SUB_COMMENT}" "${PUBSUB_TOPIC_COMMENT}"
create_sub_if_not_exists "${PUBSUB_SUB_REACTION}" "${PUBSUB_TOPIC_REACTION}"

echo
echo "所有 Pub/Sub topics 與 subscriptions 準備完成。"

