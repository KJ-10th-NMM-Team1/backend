#!/bin/bash
set -euo pipefail

APP_DIR="/home/ubuntu/app"
COMPOSE_FILE="$APP_DIR/docker-compose-prod.yml"
REMOVE_IMAGES="${REMOVE_IMAGES:-true}"

if [ ! -f "$COMPOSE_FILE" ]; then
  echo "docker compose 파일을 찾을 수 없습니다: $COMPOSE_FILE (이미 중지된 것으로 간주)"
  exit 0
fi

echo "docker compose 로그 스트리머 종료..."
pkill -f "docker compose -f $COMPOSE_FILE logs -f" >/dev/null 2>&1 || true

cd "$APP_DIR"
DOWN_FLAGS=(--remove-orphans)
if [[ "${REMOVE_IMAGES,,}" == "true" ]]; then
  echo "도커 이미지까지 삭제하도록 설정되어 있습니다 (REMOVE_IMAGES=true)."
  DOWN_FLAGS+=(--rmi local)
else
  echo "도커 이미지는 유지합니다 (REMOVE_IMAGES=false)."
fi

echo "Docker 스택 종료 중..."
docker compose -f "$COMPOSE_FILE" down "${DOWN_FLAGS[@]}" || true

echo "서버 중지 명령이 실행되었습니다."
echo "Life Cycle - ApplicationStop: complete."
