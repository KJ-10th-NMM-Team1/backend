#!/bin/bash
# (중요) 스크립트가 하나라도 실패하면 즉시 중지
set -e
set -o pipefail

APP_DIR="/home/ubuntu/app"
ENV_FILE="$APP_DIR/.env"
COOKIE_FILE="$APP_DIR/youtube_cookies.txt" # 경로 변수
GCP_SA_FILE="$APP_DIR/gcp-sa.json" # GCP SA 파일 경로

echo "Fetching secrets from Secrets Manager (aws-dupliot-app/env)..."
# 1. AWS Secrets Manager에서 JSON을 '한 번만' 가져옵니다.
SECRET_JSON=$(aws secretsmanager get-secret-value \
    --secret-id "aws-dupliot-app/env" \
    --region ap-northeast-2 \
    --query SecretString \
    --output text)

# 2. .env 파일 생성 (jq로 Key=Value 변환)
echo "Creating .env file..."
echo "$SECRET_JSON" | jq -r 'to_entries|map("\(.key)=\(.value)")|.[]' > "$ENV_FILE"

# 3. YouTube 쿠키 파일 생성 (YOUTUBE_COOKIE 키의 값을 추출)
#    (jq -r는 여러 줄 텍스트를 올바르게 처리합니다.)
echo "Creating YouTube cookie file..."
echo "$SECRET_JSON" | jq -r '.YOUTUBE_COOKIE' > "$COOKIE_FILE"

# 4. GCP SA 파일 생성 (GCP_SERVICE_ACCOUNT_JSON 키의 값을 추출)
#    (jq -r는 여러 줄의 JSON 객체를 올바르게 처리합니다.)
echo "Creating GCP service account file..."
echo "$SECRET_JSON" | jq -r '.GCP_SERVICE_ACCOUNT_JSON' > "$GCP_SA_FILE"

# 5. 생성된 모든 파일에 대한 권한 설정
chown ubuntu:ubuntu "$ENV_FILE" "$COOKIE_FILE" "$GCP_SA_FILE"
chmod 600 "$ENV_FILE" "$COOKIE_FILE" "$GCP_SA_FILE"

echo "All files created successfully."