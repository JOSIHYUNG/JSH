# JSH 개발 문서

> 이 문서는 JSH의 구현 상태, 변경 이력, 검증 결과, 기술 결정을 한 곳에서 추적하는 운영 문서다. 제품 요구사항과 상세 설계의 원문은 각 참조 문서에 두고, 이 문서에는 실제 코드와 문서가 현재 어떤 상태인지 기록한다.

## 1. 문서 메타데이터

| 항목 | 값 |
|---|---|
| 프로젝트 | JSH Personal Second Brain |
| 문서 상태 | Active |
| 기준일 | 2026-07-31 |
| 최근 갱신 | 2026-07-31 — 디자인 문서 정본 통합 |
| 운영 방식 | 단일 로컬 사용자, 인증 없음 |
| 주 실행 환경 | Windows, Python 3.12, Node.js/npm |
| 기준 브랜치 | `main` |
| 요구사항 원문 | [`PRD.md`](./PRD.md) |

## 2. 이 문서가 다루는 범위

### 포함

- 기능·구조·설계 변경의 의도와 영향
- 백엔드·프론트엔드의 구현 상태
- API, DB migration, 외부 연동, 프롬프트 변경 이력
- 실행·테스트·수동 검증 결과
- 미완료 작업, 알려진 위험, 다음 개발 범위
- 중요한 기술 결정과 결정 근거

### 제외

- 제품 요구사항의 원문: [`PRD.md`](./PRD.md)
- 데이터 구조의 정본: [`01_database_model.md`](./01_database_model.md)
- API 계약의 정본: [`02_api_spec.md`](./02_api_spec.md)
- 디자인 방향·토큰·컴포넌트 계약의 정본: [`03_design_system.md`](./03_design_system.md)
- 모듈 구조의 정본: [`04_backend_architecture.md`](./04_backend_architecture.md), [`05_frontend_architecture.md`](./05_frontend_architecture.md)
- Agent 구현 계획의 정본: [`implementation/agent-plan.md`](./implementation/agent-plan.md)
- OpenAI 사용 계약의 정본: [`external/openai.md`](./external/openai.md)

## 3. 프로젝트 기준선

### 3.1 제품 목표

개인 텍스트 자료를 문서·청크·개념·관계로 구조화하고, 3D 지식 그래프 탐색과 근거 기반 Agent 질문으로 재사용할 수 있게 한다.

### 3.2 확정된 주요 범위

- `.txt`, `.md`, `.pdf` 자료 입력 및 원문 로컬 저장
- 문서 청킹, 개념·별칭·관계 추출, 그래프 반영
- SQLite/FTS5 기반 로컬 조회와 OpenAI Vector Store 의미 검색
- 그래프 회전·확대·이동, 노드 선택, 문서·개념 상세 탐색
- 문서·대화·질문 CRUD
- `search_knowledge`, `explore_node`, OpenAI hosted `web_search`를 사용하는 탐색형 Agent
- 최대 Agent 30 turn, 최근 대화 3개만 context로 사용, 실행 과정 SSE 표시
- `[S1]` 로컬 근거와 `[W1]` 웹 출처를 분리한 출처 표시
- 다크/라이트 테마 및 반응형 UI
- 로컬 STDIO MCP Server에서 기존 지식 탐색 로직 재사용

### 3.3 기술 기준

| 영역 | 기준 구현 |
|---|---|
| Backend | Python 3.12, FastAPI, SQLModel, Alembic |
| Database | SQLite, SQLite FTS5 |
| Storage | 로컬 파일 시스템 |
| AI | OpenAI Python SDK, Responses API, Vector Store |
| Frontend | React, TypeScript, Vite |
| Graph | `react-force-graph-3d` |
| Async UX | FastAPI background task + SSE, polling fallback |
| MCP | Python MCP SDK, STDIO, `backend/app/mcp/server.py` |

### 3.4 실행 진입점

| 목적 | 위치/명령 |
|---|---|
| Backend | `backend/app/main.py` / `python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000` |
| Frontend | `frontend/` / `npm run dev` |
| DB migration | `backend/` / `python -m alembic upgrade head` |
| MCP | `backend/` / `python -m app.mcp.server` |
| API 문서 | `http://127.0.0.1:8000/docs` |
| Frontend | `http://localhost:5173/` |

## 4. 문서와 코드의 변경 순서

변경은 다음 순서로 검토한다. 이미 알고 있는 내용이라도 각 범위 시작 시 관련 문서와 코드를 다시 읽는다.

1. 요구사항 확인: [`PRD.md`](./PRD.md)에서 사용자 목표·수용 기준·우선순위를 확인한다.
2. 영향 문서 확인: DB, API, 디자인, Backend/Frontend architecture, Agent 계획 중 관련 범위를 확인한다.
3. 현재 코드 확인: 실제 route·schema·model·service·hook·component·prompt를 검색한다.
4. 변경 설계: 영향 범위, 상태 전이, 오류·빈 상태, 하위 호환을 결정한다.
5. 문서 선반영: 계약이 바뀌면 관련 명세를 먼저 수정한다.
6. 구현: 백엔드와 프론트엔드를 모듈 경계에 맞춰 수정한다.
7. 검증: migration, backend test, frontend lint/build, API 또는 화면 smoke test를 실행한다.
8. 역방향 검토: 구현 결과를 기준으로 architecture → API/DB/design → PRD 순서로 누락·불일치를 확인한다.
9. 이 문서 갱신: 아래 변경 기록과 검증 기록을 실제 결과 기준으로 작성한다.

## 5. 현재 구현 상태

상태 표기: `완료`는 코드와 관련 문서에 반영된 범위, `부분`은 핵심 동작은 있으나 운영 고도화가 남은 범위, `예정`은 아직 구현하지 않은 범위다.

| 영역 | 상태 | 현재 구현 요약 | 남은 핵심 과제 |
|---|---|---|---|
| 문서 입력·CRUD | 완료 | 입력/업로드, 원문 저장, 조회·수정·삭제·재분석 route | 대용량 파일·취소·복구 시나리오 강화 |
| 분석 workflow | 완료 | background job, 단계 상태, SSE/polling, 청크·개념·관계 적재 | durable worker 및 재시도 정책 |
| DB/migration | 완료 | SQLModel 모델과 Alembic migration, Agent 실행/이벤트 테이블 | repository 계층 분리 강화 |
| 그래프 | 완료 | graph snapshot, 필터·focus·키보드 노드 목록, 3D 렌더링 | 대형 그래프 clustering/subgraph pagination |
| 기본 검색/RAG | 완료 | Vector Store gateway, FTS5 fallback, local source mapping | 검색 품질 평가셋과 랭킹 튜닝 |
| 대화/질문 | 완료 | conversation/turn/history, rerun/delete, 최근 context | 고급 필터·정렬, 운영 지표 |
| 탐색형 Agent | 완료 | orchestrator, 3개 도구, 30 turn 제한, prompt 외부화, 실행 이벤트 | 장시간 실행 worker, 비용·관측성 강화 |
| 웹 출처 | 완료 | hosted web search, `[Wn]` citation, 출처 카드·링크 | URL 메타데이터 정규화·중복 제거 고도화 |
| Agent UI | 완료 | 활동 timeline, thinking/running 상태, SSE replay, polling fallback | component/integration/visual regression 자동화 |
| MCP | 완료 | 기존 Agent tool 로직을 import하는 STDIO server | Codex 등록 환경별 smoke test 자동화 |
| 테마/디자인 | 완료 | dark/light, 우주 테마 토큰, 반응형 그래프·패널 | 실제 화면 회귀 캡처 체계 |

## 6. 현재 코드 모듈 지도

### 6.1 Backend

```text
backend/app/
├─ api/routes/              HTTP endpoint와 SSE
├─ agent/                   Agent orchestrator, contracts, tool registry, prompts loader
├─ core/                    settings, error, envelope, HTTP 공통 정책
├─ db/                      SQLModel engine/session
├─ integrations/
│  ├─ filesystem/           원문 파일 저장
│  └─ openai/               Responses, Vector Store gateway
├─ models/                  SQLModel persistence model
├─ prompts/agent/           system/tool markdown, JSON contract/config
├─ schemas/                 API request/response DTO
├─ services/                문서·분석·그래프·검색·질문·Agent application service
└─ mcp/                     STDIO MCP entrypoint
```

### 6.2 Frontend

```text
frontend/src/
├─ api/                     backend client와 Agent SSE client
├─ app/                     provider, theme, composition, error boundary
├─ components/primitives/   공통 Button, Badge, Icon
├─ domain/                  API/domain type
├─ features/
│  ├─ documents/            입력, 상세, 최근 문서
│  ├─ concepts/             개념 상세
│  ├─ graph/                3D graph, filter, legend, node list
│  ├─ questions/             conversation, Agent timeline, source card
│  └─ shell/                top bar, question bar, system status
├─ hooks/                   화면 controller와 SSE/polling hook
└─ styles/                  token, layout, graph style
```

## 7. 기능 변경 기록

이 절은 커밋 목록을 복제하지 않는다. 사용자에게 의미 있는 기능·계약·구조 변경만 기록한다. 최신 항목을 위에 둔다.

### 2026-07-31 — Changed 디자인 문서 정본 통합

#### 의도

중복된 두 디자인 문서의 기준 충돌을 제거하고, 개발자가 참조할 단일 시각 시스템 문서를 만든다.

#### 반영

- `docs/design.md`의 Celestial Editorial 방향, 화면 구성, 테마 시스템, 구현 규칙, P0~P5 적용 순서를 `docs/03_design_system.md`에 통합
- 현재 `tokens.css`와 실제 레이아웃을 기준으로 폰트·radius·max-width 값을 정리
- README, PRD, Frontend Architecture, Agent 계획, DEVELOPMENT 문서의 디자인 정본 경로를 `docs/03_design_system.md`로 통일
- 중복된 `docs/design.md` 삭제

#### 검증

- 저장소 전체에서 `design.md` 잔여 참조 없음
- `03_design_system.md`에 시각 방향·토큰·컴포넌트·레이아웃·테마·Agent UI·QA·릴리스 순서 존재 확인
- `git diff --check` 통과

#### 후속

- 이후 디자인 변경은 `docs/03_design_system.md`만 수정한다.
- 디자인 계약이 바뀌면 `frontend/src/styles/tokens.css`, 관련 component/style, 이 문서를 같은 작업에서 갱신한다.

### 2026-07-31 — 개발 문서 운영 기준 도입

#### 의도

기획·설계·구현·검증이 분리되어 변경 누락이 생기지 않도록 단일 개발 기록을 도입한다.

#### 반영

- 이 문서 생성
- 프로젝트 기준선, 현재 구현 상태, 문서-코드 변경 순서 정의
- 이후 변경 시 기록할 템플릿과 검증 체크리스트 정의
- Keep a Changelog식 변경 분류와 MADR식 결정 기록을 통합

#### 검증

- 기존 `docs/` 명세와 Backend/Frontend 주요 모듈 목록 확인
- Agent API, prompt, MCP, SSE/polling 관련 구현 위치 확인
- 현재 working tree에 기존 사용자 변경이 존재함을 확인; 해당 변경은 덮어쓰지 않음

#### 후속

- 다음 기능 변경부터 아래 “변경 기록 템플릿”을 사용한다.
- API/DB/화면 계약이 바뀌면 본 문서만 수정하지 말고 해당 정본 문서도 함께 수정한다.

## 8. 변경 기록 템플릿

새 기능·버그 수정·구조 변경마다 다음 형식으로 이 문서의 “기능 변경 기록” 상단에 추가한다.

```md
### YYYY-MM-DD — [Added|Changed|Fixed|Removed] 변경 제목

#### 의도
사용자 문제, 버그, 기술적 필요를 한 문장으로 기록한다.

#### 영향 범위
- Backend: route/schema/service/model/integration
- Frontend: api/domain/hook/component/style
- Docs: 변경한 정본 문서
- Migration/Config: migration, env, prompt, MCP 여부

#### 반영
- 실제 구현 내용을 사용자 동작과 모듈 단위로 요약한다.
- API/DB 계약이 바뀌었으면 호환성 및 마이그레이션을 적는다.

#### 검증
- 명령: `...`
- 결과: 통과/실패 및 핵심 오류
- 수동 확인: 화면·API·SSE·외부 연동 결과

#### 위험과 후속
- 남은 문제, 롤백 방법, 다음 작업을 기록한다.

#### 관련 문서
- [`PRD.md`](./PRD.md)
- 관련 설계 문서 링크
```

## 9. 설계 결정 기록

중요한 결정은 단순히 “무엇을 했다”로 끝내지 않고, 배경·대안·결과를 남긴다. 기존 정본과 충돌하면 이 문서에 임시로 적지 말고 정본 문서와 함께 수정한다.

| 결정 | 선택 | 이유 | 영향 |
|---|---|---|---|
| 저장 DB | SQLite + SQLModel + Alembic | 단일 로컬 사용자 MVP의 운영 복잡도 최소화 | 동시 사용자·수평 확장은 범위 밖 |
| 텍스트 검색 | OpenAI Vector Store + SQLite FTS5 fallback | 의미 검색 품질과 로컬 장애 대응을 함께 확보 | provider 상태를 UI에 구분 표시 |
| Agent 흐름 | tool call 결과를 포함해 Responses API를 반복 호출 | 질문별 탐색 깊이와 도구 선택을 모델에 위임 | 최대 30 turn, timeout/cancel 필요 |
| 대화 context | 최근 사용자 메시지 3개와 이어진 응답만 사용 | 요약 저장 없이 구현 복잡도·비용 제한 | 오래된 맥락은 자동 보존하지 않음 |
| 도구 | `search_knowledge`, `explore_node`, hosted `web_search` | 내부 지식·그래프·외부 최신성의 역할 분리 | 도구 오류를 Agent에 재전달해야 함 |
| 실행 UX | durable event + SSE replay + polling fallback | 답변 생성 상태와 도구 탐색을 사용자에게 표시 | 이벤트 payload는 bounded·비민감 정보만 저장 |
| 프롬프트 | Markdown/JSON 외부 파일 로드 | 하드코딩 없이 정책·계약을 검토/교체 | 파일 누락·버전 불일치 검증 필요 |
| MCP | 기존 Agent tool을 import하여 STDIO 노출 | 로직 중복과 결과 불일치 방지 | Codex 실행 환경에 별도 등록 필요 |
| 출처 표시 | 로컬 `[S#]`, 웹 `[W#]` 분리 | 출처 종류를 즉시 구분하고 링크/문서 탐색 제공 | 답변 내 citation key 정규화 필요 |

## 10. 검증 기준

### 10.1 변경 전 영향 분석

- [ ] 요구사항과 수용 기준 확인
- [ ] 관련 API/DB/design/architecture 문서 확인
- [ ] 기존 route, schema, model, service, hook, component, prompt 검색
- [ ] 기존 동작과 호환성 영향 기록

### 10.2 변경 후 자동 검증

- [ ] Backend: `python -m alembic upgrade head`
- [ ] Backend: `python -m pytest -q`
- [ ] Frontend: `npm run lint`
- [ ] Frontend: `npm run build`
- [ ] 변경된 API/DTO에 대한 contract 확인
- [ ] 문서 변경 시 링크·heading·코드 경로 확인

### 10.3 핵심 수동 검증

- [ ] 자료 추가: 입력 → 원문 저장 → 분석 → 그래프 반영
- [ ] 문서 CRUD: 상세 → 수정 → 삭제 → 그래프/검색 반영
- [ ] 그래프: 초기 정렬, resize, 중심 이동, 노드 상세, 다크/라이트
- [ ] Agent: 답변 대기 상태 → tool timeline → 최종 답변 → `[S#]`/`[W#]` 출처
- [ ] Agent 실패·취소·30 turn 종료·SSE 재연결
- [ ] MCP: `search_knowledge`, `explore_node`가 동일한 내부 로직을 호출하는지 확인

### 10.4 검증 기록 원칙

- 실행하지 않은 검증은 통과로 표시하지 않는다.
- 외부 API key가 필요한 검증은 “환경 미설정”과 “기능 실패”를 구분한다.
- 테스트 실패를 수정하지 못한 채 문서를 갱신할 때는 오류와 재현 명령을 함께 남긴다.
- 화면 변경은 가능하면 데스크톱·좁은 화면·다크·라이트 상태를 모두 확인한다.

## 11. 알려진 위험과 우선순위

| 우선순위 | 위험/부족 사항 | 대응 방향 |
|---|---|---|
| P1 | BackgroundTasks는 프로세스 종료 시 장기 작업을 보장하지 않음 | durable worker/queue 경계 도입 검토 |
| P1 | Agent·분석 작업의 외부 API 비용과 지연이 제한되지 않을 수 있음 | timeout, budget, retry/backoff, usage 기록 강화 |
| P1 | 큰 그래프에서 3D 렌더링과 탐색성이 저하될 수 있음 | server-side subgraph, clustering, pagination 검토 |
| P2 | 검색 품질을 정량적으로 평가할 데이터셋이 없음 | 대표 질문·정답 청크 평가셋 작성 |
| P2 | PDF 텍스트 추출은 표·스캔·레이아웃 손실 가능 | OCR/추출 실패 상태와 사용자 안내 강화 |
| P2 | 웹 결과의 URL·사이트 설명·중복 출처 품질 편차 | citation normalization 및 metadata fallback 강화 |
| P3 | 자동화된 visual/integration regression이 부족함 | 핵심 화면 fixture와 CI 검증 추가 |
| P3 | 로컬 데이터 백업·복구 절차가 운영 문서화되지 않음 | DB·원문·Vector Store 매핑 백업 절차 정의 |

## 12. 다음 개발 시 작업 규칙

1. 작업 시작 메시지 또는 계획에 수정할 문서와 코드를 명시한다.
2. 범위를 Backend, Frontend, DB/API, Prompt/Agent, Design, Verification 중 하나 이상으로 분리한다.
3. 각 범위 시작 전에 구현계획·관련 명세·관련 코드를 다시 읽는다.
4. 범위 완료 즉시 테스트 결과와 문서 변경을 기록한다.
5. 다음 범위로 넘어가기 전에 API/DB/화면 계약의 불일치를 확인한다.
6. 작업 종료 시 이 문서의 변경 기록, 현재 상태, 위험/후속 작업을 갱신한다.
7. 커밋 전 `git diff --check`와 핵심 build/test를 실행한다.

## 13. 참고한 양식과 적용 이유

### Keep a Changelog

변경 이력은 기계적인 커밋 복제가 아니라 사람이 이해할 수 있는 주요 변경을 최신순으로 기록하고, `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security` 같은 분류를 사용한다는 원칙을 참고했다.

- 공식 문서: <https://keepachangelog.com/en/2.0.0/>
- 적용 영역: 7장 기능 변경 기록, 8장 변경 기록 템플릿

### MADR 4.0

중요한 기술 결정을 `Context and Problem Statement`, `Considered Options`, `Decision Outcome`, `Consequences`로 남기는 Markdown ADR 형식을 참고했다. 선택 이유와 대안을 남겨 향후 재검토 가능하게 했다.

- 공식 프로젝트: <https://adr.github.io/madr/>
- 템플릿/예시: <https://adr.github.io/madr/decisions/0000-use-markdown-architectural-decision-records.html>
- 적용 영역: 9장 설계 결정 기록

### AWS Prescriptive Guidance — ADR

ADR을 팀 개발 프로세스에 포함하고, 중요한 아키텍처 선택을 문서화해 유지보수·온보딩·후속 의사결정을 돕는다는 기업 공개 가이드를 참고했다.

- 공식 문서: <https://docs.aws.amazon.com/prescriptive-guidance/latest/architectural-decision-records/adr-process.html>
- 적용 영역: 변경 전 영향 분석, 결정 기록, 정본 문서와의 동기화 규칙

### Engineering Design Document 관행

목표, 범위, 현재 상태, 설계·구현, 검증, 위험, 후속 작업을 한 문서에서 추적하는 기업형 설계 문서 관행을 적용했다. 다만 JSH는 이미 PRD와 상세 설계 문서가 있으므로, 이 문서에는 설계 전문을 복제하지 않고 실제 개발 상태와 변경 연결 정보만 둔다.

- 참고한 공개 관행: Google 계열의 Engineering Practices 및 공개 설계 문서 관행
- 참고 설명: <https://google.github.io/eng-practices/>
- 적용 영역: 3~6장 기준선·구조·상태, 10~12장 검증·위험·운영 규칙

## 14. 유지보수 약속

앞으로의 모든 개발 작업은 코드 변경과 함께 이 문서를 갱신한다. 특히 다음 변경은 반드시 같은 작업에서 기록한다.

- 새로운 기능, API, DB table/column, migration
- Agent tool, prompt, model, context, turn/timeout 정책 변경
- Frontend 화면·상태·출처 표시·디자인 토큰 변경
- 외부 연동 또는 환경변수 변경
- 버그 수정과 재발 방지 검증
- 테스트·빌드·수동 검증 결과의 변경

문서와 코드가 다르면 코드를 기준으로 덮어쓰지 않고, 먼저 어느 쪽이 정본이어야 하는지 결정한 뒤 양쪽을 동기화한다.
