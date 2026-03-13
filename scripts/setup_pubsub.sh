#!/usr/bin/env bash

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"

if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "(unset)" ]]; then
  echo "ERROR: PROJECT_ID 未設定，請先執行："
  echo "  gcloud config set project <PROJECT_ID>"
  echo "或在環境中 export PROJECT_ID。"
  exit 1
fi

PUBSUB_TOPIC_POST="${PUBSUB_TOPIC_POST:-forum-post-events}"
PUBSUB_TOPIC_COMMENT="${PUBSUB_TOPIC_COMMENT:-forum-comment-events}"
PUBSUB_TOPIC_REACTION="${PUBSUB_TOPIC_REACTION:-forum-reaction-events}"

echo "使用專案：${PROJECT_ID}"
echo "Post topic:     ${PUBSUB_TOPIC_POST}"
echo "Comment topic:  ${PUBSUB_TOPIC_COMMENT}"
echo "Reaction topic: ${PUBSUB_TOPIC_REACTION}"
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
echo "所有 Pub/Sub topics 準備完成。"

