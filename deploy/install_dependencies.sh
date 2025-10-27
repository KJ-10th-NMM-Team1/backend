#!/bin/bash

# 이 스크립트는 appspec.yml의 BeforeInstall 훅에서 실행됩니다.

# 1. 애플리케이션 디렉토리로 이동
#    appspec.yml의 'destination' 경로와 일치해야 합니다.
APP_DIR="/home/ubuntu/app"
cd $APP_DIR

echo "Current directory: $(pwd)"

# 2. (필수 선행 작업)
#    EC2 인스턴스에 python3와 venv 모듈이 설치되어 있어야 합니다.
#    (예: sudo apt install python3-venv -y)

# 3. Python 가상 환경(venv) 생성
#    (배포 시마다 새로 생성하는 것이 가장 깔끔합니다)
echo "Creating Python virtual environment..."
if [ -d "venv" ]; then
    echo "Removing existing venv..."
    rm -rf venv
fi
python3 -m venv venv

# 4. 가상 환경 활성화
echo "Activating virtual environment..."
source venv/bin/activate

# 5. 가상 환경 내 pip 업그레이드
echo "Upgrading pip..."
pip install --upgrade pip

# 6. requirements.txt 파일에서 의존성 설치
echo "Installing dependencies from requirements.txt..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo "ERROR: requirements.txt file not found in $APP_DIR"
    # requirements.txt가 없으면 배포를 실패시킵니다.
    exit 1
fi

echo "Dependency installation complete."

# 7. (선택) venv 비활성화
#    스크립트가 종료되면 자동으로 비활성화되므로 꼭 필요하진 않습니다.
# deactivate