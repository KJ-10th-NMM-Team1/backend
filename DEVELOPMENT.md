# 개발 가이드

## 워커 콜백 로컬 테스트 방법

### 1. 빠른 테스트 (Swagger UI)

1. **API 서버 실행**
   ```bash
   docker compose up -d
   docker compose logs -f api
   ```

2. **Swagger UI 접속**
   - http://localhost:8000/docs

3. **Job 생성**
   - 프로젝트를 먼저 생성하거나 기존 프로젝트 사용
   - Job 생성 API 호출 또는 `/api/jobs/project/{project_id}` 에서 기존 job_id 확인

4. **콜백 시뮬레이션**
   - `POST /api/jobs/{job_id}/status` 엔드포인트 사용
   - Request Body 예시:
     ```json
     {
       "status": "done",
       "result_key": "projects/xxx/output.mp4",
       "metadata": {
         "stage": "done",
         "target_lang": "en",
         "segments": [
           {
             "seg_idx": 0,
             "speaker": "SPEAKER_00",
             "start": 0.217,
             "end": 13.426,
             "prompt_text": "Translated text"
           }
         ]
       }
     }
     ```

### 2. 스크립트를 이용한 테스트

#### Python 스크립트 (추천)
```bash
# 설치
pip install requests

# 전체 파이프라인 테스트
python test_worker_callback.py <job_id> --stage all --format legacy --verify

# Done 단계만 (새 포맷)
python test_worker_callback.py <job_id> --stage done --format new --upload-metadata --verify

# 특정 stage 테스트
python test_worker_callback.py <job_id> --stage asr_completed --target-lang en
```

상세 사용법: [TEST_WORKER_CALLBACK.md](TEST_WORKER_CALLBACK.md)

#### Bash 스크립트
```bash
# 전체 파이프라인
./test_worker_callback.sh <job_id> all

# Done 단계만
./test_worker_callback.sh <job_id> done
```

### 3. 실시간 모니터링

```bash
# 프로젝트 상태 한 번 조회
python monitor_pipeline.py <project_id>

# 실시간 모니터링 (자동 갱신)
python monitor_pipeline.py <project_id> --watch

# 상태 스냅샷 저장
python monitor_pipeline.py <project_id> --export before.json
# ... 작업 수행 ...
python monitor_pipeline.py <project_id> --export after.json

# 두 스냅샷 비교
python monitor_pipeline.py <project_id> --compare before.json after.json
```

### 4. 자동화된 통합 테스트

```bash
# pytest 설치
pip install pytest pytest-asyncio httpx

# 전체 테스트 실행
pytest tests/integration/test_worker_callback_flow.py -v

# 특정 테스트만 실행
pytest tests/integration/test_worker_callback_flow.py::test_full_pipeline_legacy_format -v

# 상세 로그와 함께 실행
pytest tests/integration/test_worker_callback_flow.py -v -s
```

## 디버깅 팁

### 1. 로그 확인

**API 로그**
```bash
# 전체 로그
docker compose logs -f api

# 세그먼트/에셋 관련 로그만
docker compose logs -f api | grep -E "(segment|asset|Processing|Created)"

# 에러만
docker compose logs -f api | grep -i error
```

**실시간 로그 + 필터링**
```bash
# 특정 project_id 관련 로그만
docker compose logs -f api | grep "project_id_here"

# 특정 stage 로그만
docker compose logs -f api | grep "stage: done"
```

### 2. Database 직접 확인

```bash
# MongoDB 접속
docker exec -it dupilot-mongo mongosh -u root -p example --authenticationDatabase admin dupilot

# 유용한 쿼리들
```

```javascript
// Segments 확인
db.project_segments.find({project_id: "your-project-id"}).pretty()
db.project_segments.countDocuments({project_id: "your-project-id"})

// Translations 확인
db.segment_translations.find({language_code: "en"}).pretty()

// 특정 segment의 모든 번역
const segId = "segment_id_here"
db.segment_translations.find({segment_id: segId}).pretty()

// Assets 확인
db.assets.find({project_id: "your-project-id"}).pretty()

// Project Targets 상태
db.project_targets.find({project_id: "your-project-id"}).pretty()

// Jobs 상태
db.jobs.find({project_id: "your-project-id"}).pretty()

// 최근 업데이트된 documents
db.project_segments.find().sort({updated_at: -1}).limit(5).pretty()

// 통계
db.project_segments.aggregate([
  {$match: {project_id: "your-project-id"}},
  {$group: {
    _id: "$speaker_tag",
    count: {$sum: 1},
    total_duration: {$sum: {$subtract: ["$end", "$start"]}}
  }}
])
```

### 3. REST API로 확인

```bash
# Job 상태
curl http://localhost:8000/api/jobs/<job_id> | jq

# Project의 모든 Jobs
curl http://localhost:8000/api/jobs/project/<project_id> | jq

# Targets
curl http://localhost:8000/api/projects/<project_id>/targets | jq

# Segments
curl http://localhost:8000/api/segments/project/<project_id> | jq '.[0:3]'  # 처음 3개만

# Segment 개수만
curl http://localhost:8000/api/segments/project/<project_id> | jq 'length'

# Assets
curl http://localhost:8000/api/assets/project/<project_id> | jq

# 특정 언어 에셋만
curl http://localhost:8000/api/assets/project/<project_id> | jq '.[] | select(.language_code == "en")'
```

### 4. 일반적인 문제 해결

#### Segments가 생성되지 않음
**원인:**
- metadata에 segments가 없거나 형식이 잘못됨
- metadata_key가 유효하지 않음 (S3 파일 없음)

**해결:**
```bash
# 로그 확인
docker compose logs api | grep -A 5 "check_and_create_segments"

# S3 파일 확인 (새 포맷 사용시)
aws s3 ls s3://dupilot-dev-media/projects/<project_id>/

# metadata 포맷 확인
curl http://localhost:8000/api/jobs/<job_id> | jq '.metadata'
```

#### Assets가 생성되지 않음
**원인:**
- result_key가 콜백에 포함되지 않음

**해결:**
```bash
# Job의 result_key 확인
curl http://localhost:8000/api/jobs/<job_id> | jq '.result_key'

# 콜백에 result_key 포함 확인
```

#### Translation이 생성되지 않음
**원인:**
- target_lang이 metadata에 없음
- translated_texts/prompt_text가 없음

**해결:**
```bash
# 로그 확인
docker compose logs api | grep -A 10 "segment_translations"

# metadata 확인
curl http://localhost:8000/api/jobs/<job_id> | jq '.metadata | {target_lang, translations: .translations, segments: .segments | length}'
```

#### 진행도가 업데이트되지 않음
**원인:**
- stage가 metadata에 없음
- language_code를 추출하지 못함

**해결:**
```bash
# Target 상태 확인
curl http://localhost:8000/api/projects/<project_id>/targets | jq

# 로그에서 stage 처리 확인
docker compose logs api | grep -E "(stage|project_target)"
```

## 개발 워크플로우

### 새로운 기능 추가

1. **API 엔드포인트 추가**
   - `app/api/<feature>/routes.py` 또는 `router.py`에 추가
   - Pydantic 모델 정의 (`models.py`)

2. **서비스 로직 작성**
   - `app/api/<feature>/service.py`에 비즈니스 로직 구현
   - 모든 DB 작업은 async로 작성

3. **테스트 작성**
   - 단위 테스트: `tests/unit/test_<feature>.py`
   - 통합 테스트: `tests/integration/test_<feature>_flow.py`

4. **문서 업데이트**
   - CLAUDE.md 업데이트 (중요한 변경사항)
   - API 문서는 자동 생성 (FastAPI)

### 코드 스타일

```bash
# Linting (아직 설정 안됨)
# ruff check app/

# Type checking (아직 설정 안됨)
# mypy app/

# 포맷팅 (아직 설정 안됨)
# black app/
```

## 유용한 명령어 모음

### Docker

```bash
# 전체 재시작 (코드 변경 후)
docker compose restart api

# 로그 확인 (최근 100줄)
docker compose logs --tail 100 api

# 컨테이너 내부 접속
docker exec -it dupilot-backend bash

# DB 초기화 (주의!)
docker compose down -v
docker compose up -d
```

### Database

```bash
# MongoDB 백업
docker exec dupilot-mongo mongodump -u root -p example --authenticationDatabase admin -d dupilot -o /dump
docker cp dupilot-mongo:/dump ./backup

# MongoDB 복원
docker cp ./backup dupilot-mongo:/dump
docker exec dupilot-mongo mongorestore -u root -p example --authenticationDatabase admin -d dupilot /dump/dupilot
```

### API 테스트

```bash
# Health check
curl http://localhost:8000/health

# API 문서 확인
open http://localhost:8000/docs

# 특정 엔드포인트 테스트
curl -X POST http://localhost:8000/api/jobs/<job_id>/status \
  -H "Content-Type: application/json" \
  -d @test_payload.json
```

## 환경 변수

`.env` 파일에 다음 변수들을 설정:

```env
# Core
APP_ENV=dev
DB_NAME=dupilot

# MongoDB
MONGO_URL_DEV=mongodb://root:example@mongo:27017/dupilot?authSource=admin

# AWS
AWS_PROFILE=dev
AWS_REGION=ap-northeast-2
AWS_S3_BUCKET=dupilot-dev-media

# Job Processing
JOB_CALLBACK_BASE_URL=http://localhost:8000
JOB_QUEUE_URL=<your-sqs-queue-url>

# Redis
REDIS_URL=redis://redis:6379/0
```

## 참고 자료

- [CLAUDE.md](CLAUDE.md) - 프로젝트 전체 가이드
- [TEST_WORKER_CALLBACK.md](TEST_WORKER_CALLBACK.md) - 워커 콜백 테스트 가이드
- [FastAPI 문서](https://fastapi.tiangolo.com/)
- [Motor (MongoDB) 문서](https://motor.readthedocs.io/)
