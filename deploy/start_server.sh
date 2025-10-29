#!/bin/bash

# 1. 최종 배포 디렉토리
APP_DIR="/home/ubuntu/app"

# 2. 가상 환경(venv) 경로
VENV_DIR="$APP_DIR/venv/bin/activate"

# 3. (중요) 가상 환경 활성화
#    BeforeInstall 단계에서 생성한 venv를 활성화합니다.
echo "Activating virtual environment at $VENV_DIR..."
if [ ! -f "$VENV_DIR" ]; then
    echo "ERROR: Virtual environment not found at $VENV_DIR"
    exit 1
fi
source "$VENV_DIR"

# 4. 애플리케이션 코드가 있는 디렉토리로 이동
#    (main.py 파일이 있는 곳)
cd $APP_DIR

# 5. FastAPI 서버를 백그라운드로 실행 (uvicorn)
#    (이 명령어는 stop_server.sh의 pkill 명령어와 일치해야 합니다)
echo "Starting FastAPI server (uvicorn) from $APP_DIR..."
nohup uvicorn test:app --host 0.0.0.0 --port 8000 > /dev/null 2> $APP_DIR/error.log &

echo "Server successfully started. Log file is at $APP_DIR/server.log"