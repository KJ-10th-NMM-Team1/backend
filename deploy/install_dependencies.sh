#!/bin/bash

# --- (수정) 스크립트 자신의 위치를 기준으로 '루트 폴더' 찾기 ---
# $BASH_SOURCE[0]는 이 스크립트 파일의 전체 경로를 의미합니다.
# 1. 스크립트 파일이 있는 디렉토리 (예: /opt/.../deploy)
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
# 2. 그 상위 디렉토리 (압축이 풀린 루트, /opt/.../deployment-archive)
ARCHIVE_ROOT=$( dirname "$SCRIPT_DIR" )

apt-get update -y

# Docker 설치에 필요한 패키지 설치
apt-get install -y ca-certificates curl gnupg
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

# Docker 리포지토리 추가
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

# Docker 엔진 및 CLI 설치
apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin

# Docker Compose (v2) 설치
apt-get install -y docker-compose-plugin

# (선택 사항) ubuntu 사용자가 sudo 없이 docker 명령어 사용하도록 설정
usermod -aG docker ubuntu


# 3. venv가 설치될 최종 목적지
APP_DIR="/home/ubuntu/app"
VENV_DIR="$APP_DIR/venv"

# 4. venv 생성
if [ -d "$APP_DIR" ]; then
    echo "Removing existing APP directory: $APP_DIR"
    rm -rf "$VENV_DIR"
fi
echo "Create APP directory: $APP_DIR"
mkdir -p $APP_DIR

echo "Create APP venv: $VENV_DIR..."
python3.12 -m venv "$VENV_DIR"

echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

pip install --upgrade pip

REQ_FILE="$ARCHIVE_ROOT/requirements.txt" 

echo "Installing dependencies from $REQ_FILE..."
if [ -f "$REQ_FILE" ]; then
    echo "SEUCCESS: requirements.txt install"
    pip install -r "$REQ_FILE"
else
    echo "ERROR: requirements.txt not found at $REQ_FILE"
    exit 1
fi

echo "Life Cycle - BeforeInstall: complete."
