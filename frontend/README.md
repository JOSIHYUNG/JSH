# JSH Second Brain Frontend

Vite 8, React 19, TypeScript 기반 프론트엔드입니다. 개발 서버의 `/api` 요청은 `http://127.0.0.1:8000` 백엔드로 프록시되며 OpenAI API는 Backend를 통해서만 사용합니다.

3D 지식 그래프는 `react-force-graph-3d`를 사용하고 lazy chunk로 분리됩니다. API client는 표준 envelope·오류·request ID·timeout을 처리하며 분석 진행은 SSE 우선, REST polling fallback으로 연결합니다.

## 실행

```powershell
npm ci
npm run dev
```

기본 주소: <http://localhost:5173>

`npm` 명령은 `package.json`이 있는 `frontend/`에서 실행해야 합니다.

## 환경변수

`.env.example`을 `.env`로 복사합니다.

```text
VITE_API_BASE_URL=/api/v1
```

로컬 환경은 `/api/v1` 상대 경로를 사용하고 Vite proxy가 `127.0.0.1:8000` Backend로 전달합니다. `OPENAI_API_KEY`는 frontend 환경변수에 넣지 않습니다.

## 구현 경계

- `src/api`: HTTP·SSE 통신
- `src/domain`: Backend DTO와 domain type
- `src/app`: provider, error boundary, 화면 composition
- `src/features`: 문서·개념·질문·그래프·shell
- `src/hooks/useKnowledgeController.ts`: 현재 MVP 화면 orchestration
- `src/styles`: dark/light token, responsive layout, graph

그래프 canvas를 사용할 수 없는 환경에서도 keyboard node list로 동일한 entity를 열 수 있습니다. 테마는 저장된 선택을 우선하고, 선택이 없으면 OS 선호를 따릅니다.

## 검증

```powershell
npm run build
npm run lint
```

`build`는 TypeScript project build와 production bundle 생성을 함께 실행합니다. graph chunk가 초기 shell과 분리되는지 build 산출물에서 확인합니다.
