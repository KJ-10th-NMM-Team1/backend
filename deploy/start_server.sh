#!/bin/bash

# appspec.yml의 'destination' 경로
BASE_DIR="/home/ubuntu/app"

# 실제 FastAPI 코드가 있는 경로 (dev 폴더)
APP_DIR="$BASE_DIR/dev"

# 가상 환경(venv) 경로 (install_dependencies.sh에서 생성한 위치)
VENV_PATH="$BASE_DIR/venv/bin/activate"

# 1. (중요) 가상 환경 활성화
#    venv는 'dev' 폴더 밖, 즉 'app' 폴더에 생성되어 있어야 합니다.
echo "Activating virtual environment at $VENV_PATH..."
if [ -f "$VENV_PATH" ]; then
    source $VENV_PATH
else
    echo "ERROR: Virtual environment not found at $VENV_PATH"
    exit 1 # 가상 환경이 없으면 배포 실패
fi

# 2. (중요) 실제 코드(main.py)가 있는 'dev' 폴더로 이동
echo "Changing directory to $APP_DIR..."
cd $APP_DIR

# 3. FastAPI 서버를 백그라운드로 실행
#    (로그 파일은 상위 폴더인 $BASE_DIR에 저장하여 관리하기 쉽게 함)
echo "Starting FastAPI server (uvicorn) from $APP_DIR..."
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > $BASE_DIR/server.log 2>&1 &

echo "Server successfully started. Log file is at $BASE_DIR/server.log"