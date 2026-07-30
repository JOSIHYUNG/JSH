# JSH Second Brain Backend

FastAPI + SQLModel + SQLite/FTS5 + Alembic 기반 개인용 지식 저장소 API입니다.

## 실행

PowerShell에서 `backend` 디렉터리 기준:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
# 기존 DB를 사용하는 경우에도 서버 실행 전에 최신 migration을 적용합니다.
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- Swagger: http://127.0.0.1:8000/docs
- API base: http://127.0.0.1:8000/api/v1
- Health: http://127.0.0.1:8000/api/v1/health

## 환경변수

`.env.example`을 `.env`로 복사하고 `OPENAI_API_KEY`를 입력하면 OpenAI Responses API와 Vector Store가 활성화됩니다. Vector Store ID가 비어 있으면 첫 분석 시 단일 Store를 만들고 `app_settings`에 저장합니다. 기본 모델은 `gpt-5.6-terra`이며 모델·timeout·저장 위치·업로드 한도는 `.env.example`에서 확인할 수 있습니다.

API Key 없이도 로컬 SQLite FTS5와 제한된 fallback 분석으로 문서·그래프 기능이 동작합니다. AI 질문은 가짜 답변을 만들지 않고 `AI_NOT_CONFIGURED`를 반환합니다.

## 주요 API

- `POST /api/v1/documents`, `POST /api/v1/documents/upload`: 자료 등록 및 비동기 분석
- `GET /api/v1/documents`, `GET /api/v1/documents/{id}`: 목록·상세
- `PATCH /api/v1/documents/{id}`, `POST /api/v1/documents/{id}/reanalyze`: 수정·재분석
- `DELETE /api/v1/documents/{id}`: 즉시 숨김 후 외부·로컬 정리
- `GET /api/v1/documents/{id}/analysis`, `/analysis/events`: 분석 상태·SSE
- `POST /api/v1/documents/{id}/analysis/cancel`: 명시적 분석 취소
- `GET /api/v1/documents/{id}/original`: 원문 전체 또는 range
- `GET /api/v1/graph`, `GET /api/v1/concepts/{id}`: 그래프 snapshot·개념 상세
- `POST /api/v1/questions`: 단일 질문 진입점, 최대 3개 근거와 답변
- `GET /api/v1/questions`, `GET /api/v1/questions/{id}`: 질문 이력·상세
- `POST /api/v1/questions/{id}/rerun`, `DELETE /api/v1/questions/{id}`: 재실행·항목 삭제
- `GET /api/v1/health`, `GET /api/v1/system/status`: 상태 확인

모든 JSON 응답은 `data`, `meta`, `error` envelope을 사용합니다. 원문·질문 응답은 브라우저 cache를 금지하며 OpenAI key와 provider raw 오류를 노출하지 않습니다.

## 검증

```powershell
python -m alembic upgrade head
python -m pytest -q
```

테스트는 임시 SQLite DB와 storage를 만들고 Alembic head를 적용하므로 개발용 `data/app.db`를 변경하지 않습니다.
