# 팀 작업 원칙

- `main` 브랜치에 직접 푸시하지 않습니다.
- PR 올릴시, 한명의 리뷰자를 선택할 것!

# 가상환경
- 가상환경은 .venv로 만들 것!

# Docker Guide
환경 준비: backend/.env에 APP_ENV, MONGO_URL_DEV, DB_NAME 값을 설정합니다.
예: MONGO_URL_DEV=mongodb://root:example@mongo:27017/dupilot?authSource=admin
이미지 빌드: 소스나 의존성이 바뀔 때마다 docker compose build를 실행합니다.
개발 서버 실행: docker compose up -d 실행 후
API 문서: http://localhost:8000/docs
MongoDB: mongodb://localhost:27017
중지 및 정리: docker compose down으로 컨테이너만 중지/삭제하며 데이터는 유지됩니다.
볼륨까지 삭제하려면 docker compose down -v를 사용하세요.
로그 확인/디버깅: docker compose logs -f api 또는 docker compose logs mongo
프로덕션 모드 전환: .env 파일에서 APP_ENV=prod로 변경합니다.