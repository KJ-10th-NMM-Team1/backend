# 팀 작업 원칙

- `main` 브랜치에 직접 푸시하지 않습니다.
- PR 올릴시, 한명의 리뷰자를 선택할 것!

# 폴더 구조
middleware - 미들웨어 설정 파일 모음
service - 비지니스로직 모음
router - api 모음
model - db와 연동될 객체 모음
config - 설정 파일 모음

# Docker 기반 개발 환경
- VS Code에서 저장소 루트(backend)를 열어 작업하세요.
- 사전 준비: Dev Containers 확장이 설치된 VS Code가 필요합니다.
- 컨테이너 실행: Ctrl + Shift + P → Dev Containers: Rebuild and Reopen in Container를 선택하세요.
- 개발 서버 시작: 컨테이너 내부 터미널에서 uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 를 실행합니다.
- (docker-compose up 으로 실행 시 컨테이너 진입 후 서버 실행)
- 서버 중지: 실행 중인 터미널에서 Ctrl + C를 누르면 종료됩니다.

## .env파일
```env
# CORS: 리액트 개발 서버 허용
CORS_ORIGINS=http://localhost:5173
# Mongo (compose상 서비스명 mongo 기준)
MONGO_URL_DEV=mongodb://root:example@mongo:27017/dupilot?authSource=admin
# MONGO_URL_DEV=mongodb://root:example@mongo:27017/dupilot?authSource=admin
# 미리보기 샘플(원하면 나중에 S3 presigned로 교체)
SAMPLE_VIDEO_URL=https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4
SAMPLE_AUDIO_URL=https://interactive-examples.mdn.mozilla.net/media/cc0-audio/t-rex-roar.mp3
APP_ENV="dev"
DB_NAME="dupilot"
# (S3 붙일 때)
AWS_S3_BUCKET="dupilot-dev-media"
AWS_REGION=ap-northeast-2
# Job pipeline (dev 기본값; 실서비스는 실제 호스트/큐 URL로 교체)
JOB_CALLBACK_BASE_URL=http://host.docker.internal:8000
JOB_QUEUE_URL=https://sqs.ap-northeast-2.amazonaws.com/148761638563/dupilot-queue.fifo
JOB_QUEUE_FIFO=True
JOB_TARGET_LANG=en
JOB_SOURCE_LANG=ko
JOB_RESULT_VIDEO_PREFIX=projects/{project_id}/outputs/videos/{job_id}.mp4
JOB_RESULT_METADATA_PREFIX=projects/{project_id}/outputs/metadata/{job_id}.json
JOB_QUEUE_WAIT=20
JOB_VISIBILITY_TIMEOUT=300
```

```shell
$ docker-compose down -v --rmi all # 볼륨, 네트워크 이미지 전부 삭제 명령어
$ docker-compose up -d # 도커 설치 명령어
$ docker exec -it dupilot-backend bash # 백엔드 컨테이너 들어가기(종료는 exit, Ctrl + D)
$ docker exec -it dupilot-mongo bash #몽고DB 컨테이너 들어가기(종료는 exit, Ctrl + D)
```

> Dev Containers: Rebuild and Reopen in Container

API 문서: http://localhost:8000/docs
MongoDB: mongodb://localhost:27018
중지 및 정리: docker compose down으로 컨테이너만 중지/삭제하며 데이터는 유지됩니다.
로그 확인/디버깅: docker compose logs -f api 또는 docker compose logs mongo
프로덕션 모드 전환: .env 파일에서 APP_ENV=prod로 변경합니다.

