# JSH — Personal Second Brain

개인 텍스트 자료를 분석·연결해 저장하고, 3D 지식 그래프와 근거 기반 AI 질문으로 탐색하는 로컬 단일 사용자 웹서비스입니다.

## 주요 기능

- 붙여넣기 및 `.txt`, `.md`, `.pdf` 업로드
- 제목·요약·키워드와 13종 개념·관계 구조화 추출
- 문서 → 청크 → 개념과 개념 간 관계를 3D force graph로 탐색
- 문서 조회·제목/본문 수정·재분석·삭제
- OpenAI Vector Store 의미 검색과 SQLite FTS5 fallback
- 관련 근거 최대 3개 기반 AI 답변, citation과 정확한 원문 범위 이동
- 질문 이력 조회·재실행·항목 삭제
- OS 선호를 따르는 dark/light 테마

## 프로젝트 구조

```text
JSH/
├─ backend/
│  ├─ app/
│  │  ├─ api/              # FastAPI route와 dependency
│  │  ├─ core/             # 설정·오류·응답 envelope
│  │  ├─ db/               # SQLModel engine/session
│  │  ├─ integrations/     # Local FS·OpenAI 경계
│  │  ├─ models/           # SQLModel 모델
│  │  ├─ schemas/          # API DTO
│  │  └─ services/         # 분석·검색·그래프·질문 workflow
│  ├─ alembic/versions/    # DB 마이그레이션
│  ├─ tests/               # 격리된 임시 DB API/integration 테스트
│  └─ .venv/               # Python 3.12 가상환경
├─ frontend/
│  ├─ src/
│  │  ├─ api/              # Backend API·SSE client
│  │  ├─ app/              # provider·error boundary·composition
│  │  ├─ domain/           # API/domain 타입
│  │  ├─ features/         # graph/document/question/shell UI
│  │  ├─ hooks/            # 화면 controller
│  │  └─ styles/           # tokens·layout·graph
│  └─ vite.config.mjs      # `/api` → FastAPI proxy
└─ docs/                   # PRD·데이터·API·디자인·아키텍처 명세
```

## 처음 실행

Backend:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m alembic upgrade head
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend는 별도 터미널에서 실행합니다. `package.json`은 저장소 루트가 아니라 `frontend/`에 있습니다.

```powershell
cd frontend
npm ci
npm run dev
```

- Frontend: <http://localhost:5173/>
- Backend API: <http://127.0.0.1:8000/api/v1>
- Swagger: <http://127.0.0.1:8000/docs>

저장소 루트에서 `npm run build`를 실행하면 `package.json`을 찾지 못합니다. 반드시 `cd frontend` 후 실행합니다.

## OpenAI 설정

`backend/.env.example`을 `backend/.env`로 복사하고 `OPENAI_API_KEY`를 입력합니다. 기본 생성 모델은 `gpt-5.6-terra`이며 `OPENAI_CHAT_MODEL`로 바꿀 수 있습니다. `OPENAI_VECTOR_STORE_ID`가 비어 있으면 최초 적재 시 store를 생성하고 ID를 로컬 설정에 보존합니다.

키가 없으면 문서·그래프·FTS 검색은 로컬 모드로 동작하지만 AI 질문은 가짜 답변을 만들지 않고 미연결 상태를 표시합니다. 상세 계약은 [`docs/external/openai.md`](docs/external/openai.md)를 따릅니다.

Frontend의 `frontend/.env`는 `VITE_API_BASE_URL=/api/v1`로 설정되어 있으며 Vite proxy를 통해 로컬 Backend에 연결합니다. OpenAI key를 frontend에 넣지 않습니다.

## 검증

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m alembic upgrade head
python -m pytest -q

cd ..\frontend
npm run lint
npm run build
```

제품 기준은 [`docs/PRD.md`](docs/PRD.md), API 계약은 [`docs/02_api_spec.md`](docs/02_api_spec.md), 디자인 기준은 [`docs/03_design_system.md`](docs/03_design_system.md)입니다.
