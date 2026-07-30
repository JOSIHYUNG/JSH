# 05. Frontend Architecture

- 문서 상태: Reviewed / target architecture with runtime mapping
- 시각 시스템의 canonical spec: `docs/design.md`
- 기준 문서: `docs/PRD.md`, `docs/02_api_spec.md`, `docs/03_design_system.md`, `docs/04_backend_architecture.md`
- runtime: React + TypeScript + Vite
- 핵심 UX: 지식 그래프를 보면서 `AI에게 질문`하고, 답변 근거에서 원문으로 이동한다.

## 1. 구조 원칙

1. 화면은 feature 단위로 구성하고, API·domain type·UI state를 분리한다.
2. component는 fetch를 직접 호출하지 않는다. API client → query hook → component 순서를 지킨다.
3. 서버 상태와 화면 상태를 분리한다.
4. API response envelope/error를 한 곳에서 해석한다.
5. 단일 사용자이지만 loading/error/empty/stale 상태를 명시적으로 모델링한다.
6. 사용자에게는 `AI에게 질문`만 노출한다. lexical/semantic retrieval은 질문 query의 내부 단계다.
7. 3D graph는 primary data source가 아니며, accessible list/detail fallback을 항상 제공한다.

## 2. 권장 파일 구조

```text
frontend/src/
├─ main.tsx
├─ app/
│  ├─ App.tsx
│  ├─ AppProviders.tsx
│  ├─ routes.ts
│  └─ app.css
├─ api/
│  ├─ client.ts
│  ├─ errors.ts
│  ├─ documents.ts
│  ├─ original.ts
│  ├─ concepts.ts
│  ├─ questions.ts
│  ├─ graph.ts
│  ├─ system.ts
│  └─ analysisEvents.ts
├─ domain/
│  ├─ api.ts
│  ├─ documents.ts
│  ├─ concepts.ts
│  ├─ graph.ts
│  ├─ questions.ts
│  └─ jobs.ts
├─ features/
│  ├─ shell/
│  │  ├─ AppShell.tsx
│  │  ├─ TopBar.tsx
│  │  ├─ QuestionBar.tsx
│  │  └─ SystemStatus.tsx
│  ├─ graph/
│  │  ├─ KnowledgeGraph.tsx
│  │  ├─ GraphControls.tsx
│  │  ├─ GraphLegend.tsx
│  │  ├─ GraphNodeList.tsx
│  │  ├─ graphTransform.ts
│  │  └─ graphColors.ts
│  ├─ documents/
│  │  ├─ AddDocumentModal.tsx
│  │  ├─ DocumentForm.tsx
│  │  ├─ AnalysisProgress.tsx
│  │  ├─ DocumentPanel.tsx
│  │  ├─ ChunkList.tsx
│  │  ├─ RecentDocuments.tsx
│  │  └─ documentQueries.ts
│  ├─ concepts/
│  │  ├─ ConceptPanel.tsx
│  │  ├─ ConceptBadge.tsx
│  │  └─ conceptQueries.ts
│  ├─ questions/
│  │  ├─ QuestionBar.tsx
│  │  ├─ ChatPanel.tsx
│  │  ├─ QuestionResultPanel.tsx (legacy)
│  │  ├─ SourceCard.tsx
│  │  ├─ QuestionHistoryPanel.tsx
│  │  └─ questionQueries.ts
│  └─ feedback/
│     ├─ EmptyState.tsx
│     ├─ ErrorState.tsx
│     ├─ StatusBadge.tsx
│     ├─ ToastRegion.tsx
│     └─ LoadingState.tsx
├─ state/
│  ├─ uiStore.ts
│  ├─ graphStore.ts
│  └─ questionDraft.ts
├─ hooks/
│  ├─ useAnalysisEvents.ts
│  ├─ useDebouncedValue.ts
│  ├─ useEscapeKey.ts
│  └─ useMediaQuery.ts
├─ components/
│  ├─ primitives/
│  ├─ layout/
│  ├─ form/
│  └─ markdown/
├─ styles/
│  ├─ tokens.css
│  ├─ globals.css
│  ├─ typography.css
│  └─ graph.css
└─ test/
   ├─ fixtures/
   ├─ unit/
   └─ integration/
```

현재 구현은 `src/api/knowledge.ts`, `src/domain/knowledge.ts`, `App.tsx`, `src/styles/{tokens,globals,graph}.css`를 사용한다. 별도 search form은 없고 `AI에게 질문` 단일 진입으로 통합되어 있다. 멀티턴에서는 `ChatPanel`이 대화 turn과 turn별 source를 렌더링한다.

### Runtime mapping

| 목표 | 현재 | 다음 보완 |
|---|---|---|
| resource API modules/query hooks | 단일 `knowledgeApi` + `useKnowledgeController` | 기능 증가 시 resource별 client/query로 분리 |
| analysis progress | SSE 우선 + REST polling fallback | preview payload 도입 시 reducer 확장 |
| graph focus/filter | focus request, 기간·유형·강도 filter, fit/reset 연결 | 대형 graph 성능 계측 |
| source offset highlight | range API와 citation/chunk 위치 강조 연결 | 완료 |
| conversation actions | 대화 열기·turn 재실행·대화 삭제·제목 수정 | URL conversation 복원과 ChatPanel 연결 |
| application resilience | root error boundary, 요청 timeout/abort, panel별 error | component 자동 테스트 추가 |
| theme | OS 선호 초기값 + localStorage dark/light 전환 | 시각 회귀 자동화 |

## 3. 상태 분리

### 3.1 Server state

다음은 API에서 재조회 가능한 state다.

- `documents`: recent/list/detail.
- `graphSnapshot`: filters/focus 기준 snapshot.
- `conceptDetail`.
- `conversations`: recent list.
- `conversationDetail`: metadata + ordered turns.
- `questionResult`: legacy 단일 질문/현재 turn 결과.
- `systemStatus`.
- `analysisJob`; P1에서 추가할 preview events.

server state는 query key와 invalidate policy를 가진다. 동일 데이터의 수동 복사본을 여러 component state에 두지 않는다.

### 3.2 UI state

`uiStore`:

| 상태 | 타입/예 | 설명 |
|---|---|---|
| `contextPanel` | `{kind, id} or null` | document/concept/question/conversation |
| `isAddModalOpen` | boolean | 자료 추가 modal |
| `historyOpen` | boolean | 대화 기록 panel |
| `graphFilters` | object | node/concept/recent/strength |
| `graphFocus` | `{type,id} or null` | selected focus |
| `toastQueue` | Toast[] | 짧은 feedback |
| `activeModalState` | enum | idle/processing/completed/failed/canceled |

`questionDraft`:

- `value`: 현재 입력값.
- `source`: `empty/history/concept`.
- `submittedAt`.
- submit 상태는 server question query가 source of truth이며, local boolean만으로 표현하지 않는다.
- `activeConversationId`: null이면 새 대화, 값이 있으면 후속 질문.

### 3.3 상태 machine

#### Add document

`idle → validating → processing → completed`

오류: `processing → failed`; 사용자 취소: `processing → canceled`; retry: `failed/canceled → processing`.

#### Conversation question

`idle → submitting → retrieving → generating → completed`

분기:

- `no_evidence`: completed가 아니라 별도 결과 상태로 렌더링.
- network/provider error: `failed`, 입력값 보존.
- `no_evidence`: completed가 아니라 별도 결과 상태로 렌더링.
- rerun: 기존 turn을 바꾸지 않고 같은 대화에 새 turn 생성.
- 새 대화: active conversation을 비우고 첫 질문 전송 시 conversation 생성.

## 4. API client 규칙

### 4.1 `api/client.ts`

책임:

- base URL `/api/v1`.
- JSON request headers.
- `fetch` timeout/AbortSignal.
- response JSON envelope decode.
- non-2xx를 `ApiError`로 변환.
- request ID를 error object에 보존.
- timeout과 caller `AbortSignal`을 결합하고 network/timeout 오류를 표준 code로 변환.

resource 함수는 `client.request<T>()`만 사용한다. component에서 raw `fetch`를 금지한다.

### 4.2 TypeScript API types

Backend DTO와 1:1로 맞추는 타입:

- `ApiEnvelope<T>`, `ApiErrorPayload`, `PaginationMeta`.
- `DocumentSummary`, `DocumentDetail`, `DocumentChunk`, `AnalysisJob`.
- `ConceptSummary`, `ConceptDetail`, `ConceptRelation`.
- `GraphSnapshot`, `GraphNode`, `GraphEdge`.
- `QuestionResult`, `QuestionSource`, `QuestionHistorySummary`.
- `ConversationSummary`, `ConversationDetail`, `ConversationTurn`.

enum은 string union으로 선언하고 unknown enum은 `Unknown` fallback renderer를 갖는다. API가 새로운 concept type을 추가해도 전체 화면이 crash하지 않아야 한다.

### 4.3 Error handling

`ApiError` 필수 필드:

| 필드 | 설명 |
|---|---|
| `code` | backend stable code |
| `message` | 사용자 기본 문구 |
| `details` | field/action/limit |
| `retryable` | retry button 여부 |
| `status` | HTTP status |
| `requestId` | 문의/console 확인 |

render 규칙:

- `VALIDATION_ERROR`: input 아래 inline field error.
- `OPENAI_UNAVAILABLE`/`VECTOR_STORE_NOT_READY`: AI 상태 + retry; 입력/원문 보존.
- `DOCUMENT_BUSY`: 문서 panel에 현재 작업 표시.
- unknown: generic error + request ID의 축약 표시.

## 5. Query / mutation 정책

별도 상태 라이브러리를 도입하는 경우에도 아래 계약을 지킨다. 현재 MVP는 API hooks와 React state로 시작할 수 있고, server cache가 복잡해지면 TanStack Query로 교체 가능한 query interface를 유지한다.

### Query keys

| key | invalidate 시점 |
|---|---|
| `system.status` | startup, job complete/fail |
| `documents.list(filters)` | document ready/delete |
| `documents.detail(id)` | analysis complete/reanalyze/delete |
| `documents.update(id, payload)` | title-only immediate save, content edit → reanalysis |
| `graph.snapshot(filters)` | document ready/delete, concept edit |
| `concepts.detail(id)` | analysis complete, concept edit |
| `questions.list(filters)` | question complete/rerun/delete |
| `questions.detail(id)` | question complete |
| `conversations.list()` | conversation create/turn complete/delete/rename |
| `conversations.detail(id)` | turn complete/retry/delete/document stale update |

### Mutation 규칙

- upload/paste success 202 후 해당 document 분석 SSE를 우선 구독하고 연결 실패 시 REST polling으로 전환.
- analysis completed → documents list/detail + graph snapshot invalidate.
- delete 202 → 즉시 graph/list에서 optimistic hide, 실패 시 rollback + error.
- question complete → result panel open + history list invalidate.
- rerun → 기존 result 유지, 새 result를 active로 교체.

질문 POST가 `202`와 `status=queued/retrieving/generating`을 반환하면 active `ChatPanel`은 `GET /questions/{id}` 또는 conversation detail을 짧은 간격으로 polling한다. `completed/no_evidence/failed`에서 polling을 종료하고, 입력값과 기존 turn은 보존한다.

## 6. App composition

`AppShell`의 흐름:

1. `AppProviders`가 API client, theme tokens, error boundary, accessibility live region을 설치한다.
2. 초기 mount에서 `system.status`, documents recent, graph default를 병렬 조회한다.
3. graph·list 중 하나가 실패해도 다른 영역은 독립적으로 empty/error를 렌더링한다.
4. `contextPanel`이 entity를 지정하면 해당 query를 실행하고 loading skeleton을 보인다.
5. global `busy`는 사용하지 않는다. upload와 question이 서로의 interaction을 필요 이상으로 막지 않는다.

## 7. Feature 설계

### 7.1 Shell

`TopBar`:

- 자료 추가 trigger.
- 질문 기록 trigger.
- system status.
- home/reset.

`QuestionBar`:

- 단일 input.
- `AI에게 질문` submit.
- keyword/sentence/question을 동일하게 허용.
- disabled가 필요한 경우는 blank/active submit request뿐이며, 질문 validation 메시지는 inline.

### 7.2 Graph

`KnowledgeGraph`는 `react-force-graph-3d` adapter다. library가 node/link 객체를 mutation하므로 API snapshot을 clone한 뒤 simulation에 전달하고 domain snapshot은 불변으로 유지한다.

adapter 책임:

- `GraphNode` → library node.
- `GraphEdge` → library link.
- `color_token` → design token 실제 color.
- node click/hover callback을 entity key로 변환.
- link source/target가 object로 변환되는 library 특성을 안전하게 처리.

성능 정책:

- default node limit 500, edge limit 1,500.
- chunk는 default 제외.
- selection 변경 시 전체 graph를 재조회하지 않고 focus query만 실행.
- graph data identity를 안정적으로 유지해 불필요한 simulation restart를 막는다.
- 3D graph module은 `React.lazy`로 분리해 초기 shell bundle에서 제외한다. WebGL 엔진 chunk는 별도 산출물로 관리한다.
- `requestAnimationFrame` 기반 custom animation을 추가하지 않고 library particle 기능을 저강도로 사용한다.

접근성:

- `GraphNodeList`가 모든 visible node를 텍스트 목록으로 제공한다.
- 현재 선택 node와 graph canvas selection을 동기화한다.
- keyboard로 list item을 선택하면 ContextPanel을 연다.

### 7.3 Documents

`AddDocumentModal`:

- form 값은 modal local state.
- submit 후 job ID를 저장하고 `useAnalysisEvents`를 구독.
- modal close는 작업 cancel이 아니다. processing 중 닫으면 background progress indicator를 TopBar/RecentDocuments에 남긴다.
- 완료 후 `graph.focus`를 새 document로 설정.
- failed/canceled 상태에서 원문 draft를 유지하고 retry.

`DocumentPanel`:

- detail query로 metadata/chunk/concept를 표시하고, 원문은 `GET /documents/{id}/original`로 range 조회한다.
- chunk selection은 `start_char/end_char`를 original query로 전달해 해당 구간을 highlight한다.
- delete confirm은 영향 범위와 question snapshot 보존을 설명.

### 7.4 Concepts

`ConceptPanel`은 aliases/source chunks/related concepts를 section으로 나눈다.

- source chunk click → document panel open + chunk highlight.
- related concept click → panel entity replace, graph focus update.
- `이 개념으로 질문`은 questionDraft만 채우고 자동 submit하지 않는다.

### 7.5 Questions

`ChatPanel`은 active conversation을 오래된 turn부터 표시한다. 각 turn은 질문, 상태, 답변, citation marker, 관련 개념, 해당 turn의 source cards를 독립적으로 렌더링한다. 패널 하단 composer에서 바로 후속 질문을 보내며, 이전 turn은 답변 context로만 사용되고 현재 turn source와 섞지 않는다.

`ChatPanel`의 turn render 순서:

1. question header/status.
2. 검증된 plain text answer와 citation marker.
3. citation marker links.
4. source cards 1~3.
5. related concepts.
6. retry/edit question actions.

현재 답변은 raw HTML/임의 Markdown을 렌더링하지 않고 plain text와 검증된 citation marker만 표현한다. citation key가 source에 없거나 AI 생성이 실패하면 답변을 노출하지 않고 실패 상태와 검색된 근거 카드만 보여준다.

`SourceCard`:

- `openable=true`: 원문 위치로 이동.
- `openable=false`: snapshot만 표시, disabled link와 stale badge.
- same document 여러 source는 document label을 반복하지 않되 rank/citation을 보존할 수 있다.

`QuestionHistoryPanel`:

- conversation list query pagination.
- click → conversation detail query.
- 대화 삭제는 optimistic remove 후 실패 rollback.
- turn rerun은 기존 turn을 바꾸지 않고 새 turn을 만든다.
- 새 UI에서 개별 turn 삭제는 제공하지 않는다.

## 8. Analysis SSE

`useAnalysisEvents(jobId)`:

- EventSource URL을 API client base와 조합.
- 현재는 started/progress/completed/failed/canceled를 처리한다. P1 preview event가 추가되면 reducer를 확장한다.
- progress/completed/failed/canceled는 modal state에 반영한다. preview event를 추가하는 경우에도 server detail cache에 임시 저장하지 않는다.
- completed event에서 document detail/list/graph query를 invalidate한다.
- connection error는 즉시 실패로 단정하지 않고 exponential reconnect 후 REST detail로 최종 상태를 확인한다.
- modal을 닫아도 서버 작업은 취소되지 않으며 recent document 상태와 graph 재조회로 완료 결과를 회복한다. 사용자가 명시적으로 취소할 때만 cancel API를 호출한다.

## 9. Routing / URL 정책

MVP는 single-page layout으로 시작한다. 브라우저 새로고침 복원을 위해 선택 상태를 query string으로 확장할 수 있다.

권장 query:

- `?document=12`
- `?concept=7`
- `?conversation=12`
- `?question=21`
- `?focus=document:12`

URL에 원문·질문 전문을 넣지 않는다. 질문 history ID만 사용한다.

## 10. Loading / empty / error

### Initial

- graph loading: canvas 대신 starfield skeleton + `지식 구조를 불러오는 중`.
- documents loading: list skeleton.
- one query failure: 해당 card만 ErrorState.

### Empty

- no documents: `첫 자료 추가` CTA.
- no concepts: `아직 연결된 개념이 없습니다`.
- no graph after filters: filter reset + 자료 추가.
- no question evidence: `관련 자료를 찾지 못했습니다` + question edit/material add.

### Failure

- original text is never discarded because of AI failure.
- retry button preserves form/question.
- provider failure does not show stack trace or raw API message.
- request_id is shown only behind expandable `문제 신고 정보`.

## 11. Performance / resilience

- graph snapshot request는 filters 변경 debounce 150~250ms.
- QuestionBar submit은 중복 submit을 막고 AbortSignal로 이전 요청을 취소한다. 서버 history가 이미 생성된 뒤 cancel돼도 기존 결과 상태를 조회한다.
- document detail long content는 chunk list pagination/lazy loading.
- markdown answer는 큰 output에 max-height + expand.
- file upload progress는 browser upload progress가 필요할 때만 XHR/fetch wrapper를 확장하고, 분석 progress와 혼동하지 않는다.
- 3D graph는 lazy chunk로 분리하고 shell bundle 예산을 별도로 관리한다. graph chunk 경고는 WebGL 엔진 특성상 허용하되 초기 상호작용을 막지 않아야 한다.

## 12. Test architecture

### Unit

- API envelope decoder/error mapper.
- graph adapter color/type/selection.
- concept type fallback.
- question citation renderer.
- chunk highlight offset.
- reducer state transitions.

### Component

- QuestionBar: blank, 2 chars, success, retry, restored history.
- AddDocumentModal: processing close, cancel, failed retry, complete.
- SourceCard: openable/stale.
- GraphNodeList: keyboard selection.
- ErrorState/EmptyState: action callback.

### Integration

- initial graph + documents render.
- upload 202 → SSE → graph refresh.
- ask question → answer/source → source click → document highlight.
- deleted source history renders snapshot.
- API 422/502 standardized UI.

### Visual

- desktop/mobile viewport matrix from design system.
- dark/light contrast, graph panel overlap, reduced motion.
- dense graph, no evidence, processing, stale evidence screenshots.

## 13. Current implementation migration checklist

2026-07-30 역검증 결과:

- [x] API DTO 전체 타입과 표준 envelope decoder 사용.
- [x] 별도 search form 제거, `/questions` 단일 질문 UI 사용.
- [x] conversation/turn API와 `ChatPanel`을 연결하고 후속 질문 context를 유지한다.
- [x] document/chunk/concept graph와 filter query 연결.
- [x] upload text paste + `.txt/.md/.pdf` multipart 지원.
- [x] feature별 question/document/panel pending 상태 사용.
- [x] source range 조회·chunk highlight, graph focus, history rerun/delete action 연결.
- [x] SSE progress/terminal event와 polling fallback을 modal 실제 stage에 연결.
- [x] ErrorBoundary, API timeout/abort, OS theme 초기값과 dark/light 전환 구현.
- [x] graph API snapshot clone, keyboard node list, reduced-motion particle 제한 구현.
- [x] 3D graph를 lazy chunk로 분리해 초기 shell bundle을 축소.
- [ ] resource별 query hook 분리와 URL 상태 복원을 추가한다. (P3)
- [ ] component/integration/visual regression 자동 테스트를 추가한다. (P4)
- [ ] 대형 graph에서 clustering 또는 서버 side subgraph pagination을 검토한다. (P4)
