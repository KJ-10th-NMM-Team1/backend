#!/bin/bash

echo "FastAPI (uvicorn) 서버를 중지합니다..."
PIDS=$(ps -ef | grep 'uvicorn' | grep -v grep | awk '{print $2}')

if [ -z "$PIDS" ]; then
  echo "Uvicorn 프로세스가 없습니다."
  exit 0
fi

echo "종료할 PID: $PIDS"
kill -TERM $PIDS || true

echo "서버 중지 명령이 실행되었습니다."
echo "Life Cycle - ApplicationStop: complete."