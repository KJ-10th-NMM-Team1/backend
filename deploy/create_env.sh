#!/bin/bash
set -e
set -o pipefail

APP_DIR="/home/ubuntu/app"
ENV_FILE="$APP_DIR/.env"
COOKIE_FILE="$APP_DIR/youtube_cookies.txt" # <-- 1. 쿠키 파일 경로 정의

echo "Creating .env file..."
aws secretsmanager get-secret-value \
    --secret-id "aws-dupliot-app/env" \
    --region ap-northeast-2 \
    --query SecretString \
    --output text | jq -r 'to_entries|map("\(.key)=\(.value)")|.[]' > $ENV_FILE

SA_JSON=$(grep '^GCP_SERVICE_ACCOUNT_JSON='$ENV_FILE | cut -d= -f2-)
YOUTUBE_COOKIE_FILE=$(grep '^YOUTUBE_COOKIE='$ENV_FILE | cut -d= -f2-)

printf '%s\n' "$SA_JSON" > $APP_DIR/gcp-sa.json
printf '%s\n' "$YOUTUBE_COOKIE_FILE" > $APP_DIR/youtube_cookie.txt

chmod 600 /home/ubuntu/app/gcp-sa.json
chmod 600 /home/ubuntu/app/youtube_cookie.txt

chown ubuntu:ubuntu /home/ubuntu/app/.env
chmod 600 /home/ubuntu/app/.env # (보안을 위해 소유자만 읽고 쓸 수 있도록 설정)


echo ".env file created successfully."
