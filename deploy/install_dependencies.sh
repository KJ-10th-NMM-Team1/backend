#!/bin/bash

# 이 스크립트는 '임시 폴더'에서 실행됩니다.
# (appspec.yml, requirements.txt, main.py 등이 모두 여기에 있음)

echo "--- DEBUG INFO ---"
echo "Current Working Directory: $(pwd)"
echo "Listing files in CWD (deploy/):"
ls -al
echo "Listing files in Parent Directory (root/):"
ls -al ../
echo "--- END DEBUG INFO ---"

# 최종 venv가 설치될 위치
APP_DIR="/home/ubuntu/app"
VENV_DIR="$APP_DIR/venv"

# 1. venv 생성 (경로를 /home/ubuntu/app/venv로 지정)
echo "Creating venv at $VENV_DIR..."
if [ -d "$VENV_DIR" ]; then
    rm -rf "$VENV_DIR"
fi
# python3.9를 사용해 venv를 $VENV_DIR 경로에 생성
python3.9 -m venv "$VENV_DIR"

# 2. venv 활성화
echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# 3. pip 업그레이드
pip install --upgrade pip

# 4. 'requirements.txt' 설치
#    (dev 폴더가 아닌, 현재 스크립트와 같은 위치(루트)에서 찾음)
REQ_FILE="../requirements.txt"

echo "Installing dependencies from $REQ_FILE..."
if [ -f "$REQ_FILE" ]; then
    pip install -r "$REQ_FILE"
else
    # 이 에러가 뜨면 zip 파일에 requirements.txt가 빠진 것
    echo "ERROR: requirements.txt not found in the root of the zip package."
    exit 1
fi

echo "Dependency installation complete."