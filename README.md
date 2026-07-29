# JSH — Second Brain MVP

개인 텍스트 자료를 업로드하고, 검색·질답·3D 지식 그래프로 탐색하는 세컨드 브레인 MVP입니다.

## 디렉터리

```text
JSH/
├─ backend/
│  ├─ app/
│  │  ├─ api/routes/       # API 라우트
│  │  ├─ core/             # 설정
│  │  ├─ models/           # SQLModel 모델
│  │  ├─ services/         # 문서 분할·분석·임베딩
│  │  ├─ db.py
│  │  └─ main.py
│  ├─ alembic/versions/    # DB 마이그레이션
│  ├─ tests/
│  ├─ .venv/               # Python 3.12 가상환경
│  └─ pyproject.toml
└─ frontend/
   ├─ src/
   │  ├─ api/              # Backend API 클라이언트
   │  ├─ types/            # 지식 그래프 타입
   ├─ public/
   ├─ vite.config.ts       # /api → FastAPI 프록시
   └─ package.json
```

## 개발 시작

터미널 1:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
alembic upgrade head
fastapi dev app/main.py
```

터미널 2:

```powershell
cd frontend
npm run dev
```

OpenAI 분석/임베딩을 사용하려면 `backend/.env.example`을 `backend/.env`로 복사한 뒤 `OPENAI_API_KEY`를 입력합니다. 키가 없으면 로컬 키워드 분석·검색 fallback으로 실행됩니다.

Backend API 문서는 <http://127.0.0.1:8000/docs>, Frontend는 <http://localhost:5173>에서 확인할 수 있습니다.

## MVP 기능

- `.txt`, `.md`, `.pdf` 업로드 및 텍스트 추출
- 문서 요약·키워드·청크·임베딩 저장
- 키워드/문장 검색과 상위 3개 참고 문서 기반 질답
- 문서 간 유사도/키워드 연결을 3D force graph로 시각화
- 그래프 노드 클릭 시 원문 모달 표시
