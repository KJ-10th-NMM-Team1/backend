#!/bin/bash

# --- (수정) 스크립트 자신의 위치를 기준으로 '루트 폴더' 찾기 ---
# $BASH_SOURCE[0]는 이 스크립트 파일의 전체 경로를 의미합니다.
# 1. 스크립트 파일이 있는 디렉토리 (예: /opt/.../deploy)
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
# 2. 그 상위 디렉토리 (압축이 풀린 루트, /opt/.../deployment-archive)
ARCHIVE_ROOT=$( dirname "$SCRIPT_DIR" )
# ---

# 3. venv가 설치될 최종 목적지
APP_DIR="/home/ubuntu/app"
VENV_DIR="$APP_DIR/venv"

# 4. venv 생성
if [ -d "$APP_DIR" ]; then
    echo "Removing existing APP directory: $APP_DIR"
    rm -rf "$VENV_DIR"
    rm -rf "$APP_DIR"
fi
echo "Create APP directory: $APP_DIR"
mkdir -p $APP_DIR

ENV_FILE="$APP_DIR/.env"

cat <<'EOF' > "$ENV_FILE"
# CORS: 리액트 개발 서버 허용
AWS_PROFILE=dev
CORS_ORIGINS=http://localhost:5173
# Mongo (compose상 서비스명 mongo 기준)
MONGO_URL_DEV=mongodb://root:example@ec2-52-79-235-56.ap-northeast-2.compute.amazonaws.com:27017/dupilot?authSource=admin
# MONGO_URL_DEV=mongodb://best:absc3513@localhost:27017/
# 미리보기 샘플(원하면 나중에 S3 presigned로 교체)
SAMPLE_VIDEO_URL=https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4
SAMPLE_AUDIO_URL=https://interactive-examples.mdn.mozilla.net/media/cc0-audio/t-rex-roar.mp3
APP_ENV=dev
DB_NAME=dupilot
# (S3 붙일 때)
AWS_S3_BUCKET=dupilot-dev-media
AWS_REGION=ap-northeast-2
# Job pipeline (dev 기본값; 실서비스는 실제 호스트/큐 URL로 교체)
# JOB_CALLBACK_BASE_URL=http://host.docker.internal:8000
JOB_CALLBACK_BASE_URL=http://ec2-15-164-97-47.ap-northeast-2.compute.amazonaws.com:8000
JOB_QUEUE_URL=https://sqs.ap-northeast-2.amazonaws.com/148761638563/dupilot-queue.fifo
JOB_QUEUE_FIFO=True
JOB_TARGET_LANG=en
JOB_SOURCE_LANG=ko
JOB_RESULT_VIDEO_PREFIX=projects/{project_id}/outputs/videos/{job_id}.mp4
JOB_RESULT_METADATA_PREFIX=projects/{project_id}/outputs/metadata/{job_id}.json
JOB_QUEUE_WAIT=20
JOB_VISIBILITY_TIMEOUT=300

SECRET_KEY=a0b1c2d3e4f5a0b1c2d3e4f5a0b1c2d3e4f5a0b1c2d3e4f5a0b1c2d3e4f5
GOOGLE_CLIENT_ID=502610250439-1ltnk1tmom9sotu285ch49s9ktur1tb2.apps.googleusercontent.com
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
EOF

echo "Created environment file at $ENV_FILE"

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
