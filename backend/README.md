# JSH Second Brain Backend

FastAPI + SQLModel + SQLite/FTS5 + Alembic 기반 개인용 지식 저장소 API입니다.

## 실행

PowerShell에서 `backend` 디렉터리 기준:

```powershell
.\.venv\Scripts\Activate.ps1
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- Swagger: http://127.0.0.1:8000/docs
- API base: http://127.0.0.1:8000/api/v1
- Health: http://127.0.0.1:8000/api/v1/health

## 환경변수

`backend/.env`에 `OPENAI_API_KEY`를 입력하면 OpenAI Responses API와 Vector Store가 활성화됩니다. Vector Store ID가 비어 있으면 첫 분석 시 단일 Store를 만들고 `app_settings`에 저장합니다. 모델·저장 위치·업로드 한도 등은 `.env.example`에서 확인할 수 있습니다.

API Key 없이도 로컬 SQLite FTS5 검색과 fallback 분석으로 개발/데모가 동작합니다.

## 주요 API

- `POST /api/v1/documents`, `POST /api/v1/documents/upload`: 자료 등록 및 비동기 분석
- `GET /api/v1/documents/{id}/analysis/events`: 분석 SSE
- `GET /api/v1/documents/{id}`, `GET /api/v1/documents/{id}/original`: 상세·원문 range
- `GET /api/v1/graph`: 그래프 snapshot
- `POST /api/v1/questions`: 단일 질문 진입점, 최대 3개 근거와 답변
- `GET /api/v1/questions`: 질문 히스토리

모든 JSON 응답은 `data`, `meta`, `error` envelope을 사용합니다.

## 검증

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```
