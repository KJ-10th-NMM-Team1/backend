#!/bin/bash

# --- (수정) 스크립트 자신의 위치를 기준으로 '루트 폴더' 찾기 ---
# $BASH_SOURCE[0]는 이 스크립트 파일의 전체 경로를 의미합니다.
# 1. 스크립트 파일이 있는 디렉토리 (예: /opt/.../deploy)
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
# 2. 그 상위 디렉토리 (압축이 풀린 루트, /opt/.../deployment-archive)
ARCHIVE_ROOT=$( dirname "$SCRIPT_DIR" )
# ---

# (디버깅)
echo "--- NEW DEBUG INFO ---"
echo "BASH_SOURCE[0] is: ${BASH_SOURCE[0]}"
echo "SCRIPT_DIR is: $SCRIPT_DIR"
echo "ARCHIVE_ROOT is: $ARCHIVE_ROOT"
echo "Listing files in ARCHIVE_ROOT:"
ls -al "$ARCHIVE_ROOT"
echo "--- END DEBUG INFO ---"


# 3. venv가 설치될 최종 목적지
APP_DIR="/home/ubuntu/app"
VENV_DIR="$APP_DIR/venv"

# 4. venv 생성
echo "Creating venv at $VENV_DIR..."
if [ -d "$VENV_DIR" ]; then
    rm -rf "$VENV_DIR"
    rm -rf "$APP_DIR/*"
fi
python3.9 -m venv "$VENV_DIR"

# 5. venv 활성화
echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# 6. pip 업그레이드
pip install --upgrade pip

# 7. (수정) 'ARCHIVE_ROOT'의 절대 경로에서 requirements.txt 찾기
REQ_FILE="$ARCHIVE_ROOT/requirements.txt" 

echo "Installing dependencies from $REQ_FILE..."
if [ -f "$REQ_FILE" ]; then
    pip install -r "$REQ_FILE"
else
    echo "ERROR: requirements.txt not found at $REQ_FILE"
    exit 1
fi

echo "Dependency installation complete."