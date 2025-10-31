# 팀 작업 원칙

- `main` 브랜치에 직접 푸시하지 않습니다.
- PR 올릴시, 한명의 리뷰자를 선택할 것!

# 가상환경

- 가상환경은 .venv로 만들 것!

# 폴더 구조

middleware - 미들웨어 설정 파일 모음
service - 비지니스로직 모음
router - api 모음
model - db와 연동될 객체 모음
config - 설정 파일 모음

# Docker Guide

## .env파일

```env
MONGO_URL_DEV=mongodb://root:example@mongo:27017/dupilot?authSource=admin
APP_ENV="dev"
DB_NAME="dupilot"
```

```shell
$ docker-compose down -v --rmi all # 볼륨, 네트워크 이미지 전부 삭제 명령어
$ docker-compose up -d # 도커 설치 명령어
```

API 문서: http://localhost:8000/docs
MongoDB: mongodb://localhost:27017
중지 및 정리: docker compose down으로 컨테이너만 중지/삭제하며 데이터는 유지됩니다.
로그 확인/디버깅: docker compose logs -f api 또는 docker compose logs mongo
프로덕션 모드 전환: .env 파일에서 APP_ENV=prod로 변경합니다.
