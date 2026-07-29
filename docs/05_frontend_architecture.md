# 05. Frontend Architecture

- 문서 상태: Draft / Architecture baseline
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
│  │  ├─ QuestionResultPanel.tsx
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

현재 `src/api/knowledge.ts`, `src/types/knowledge.ts`, `App.tsx`, `App.css`는 각각 resource API/domain types/features로 분리한다. 현재의 별도 search form과 document-only graph는 목표 구조로 교체한다.

## 3. 상태 분리

### 3.1 Server state

다음은 API에서 재조회 가능한 state다.

- `documents`: recent/list/detail.
- `graphSnapshot`: filters/focus 기준 snapshot.
- `conceptDetail`.
- `questionHistory`.
- `questionResult`.
- `systemStatus`.
- `analysisJob`과 preview events.

server state는 query key와 invalidate policy를 가진다. 동일 데이터의 수동 복사본을 여러 component state에 두지 않는다.

### 3.2 UI state

`uiStore`:

| 상태 | 타입/예 | 설명 |
|---|---|---|
| `contextPanel` | `{kind, id} or null` | document/concept/question |
| `isAddModalOpen` | boolean | 자료 추가 modal |
| `historyOpen` | boolean | 질문 기록 panel |
| `graphFilters` | object | node/concept/recent/strength |
| `graphFocus` | `{type,id} or null` | selected focus |
| `toastQueue` | Toast[] | 짧은 feedback |
| `activeModalState` | enum | idle/processing/completed/failed/canceled |

`questionDraft`:

- `value`: 현재 입력값.
- `source`: `empty/history/concept`.
- `submittedAt`.
- submit 상태는 server question query가 source of truth이며, local boolean만으로 표현하지 않는다.

### 3.3 상태 machine

#### Add document

`idle → validating → processing → completed`

오류: `processing → failed`; 사용자 취소: `processing → canceled`; retry: `failed/canceled → processing`.

#### Question

`idle → submitting → retrieving → generating → completed`

분기:

- `no_evidence`: completed가 아니라 별도 결과 상태로 렌더링.
- network/provider error: `failed`, 입력값 보존.
- rerun: 기존 history를 바꾸지 않고 새 question result 생성.

## 4. API client 규칙

### 4.1 `api/client.ts`

책임:

- base URL `/api/v1`.
- JSON request headers.
- `fetch` timeout/AbortSignal.
- response JSON envelope decode.
- non-2xx를 `ApiError`로 변환.
- request ID를 error object에 보존.

resource 함수는 `client.request<T>()`만 사용한다. component에서 raw `fetch`를 금지한다.

### 4.2 TypeScript API types

Backend DTO와 1:1로 맞추는 타입:

- `ApiEnvelope<T>`, `ApiErrorPayload`, `PaginationMeta`.
- `DocumentSummary`, `DocumentDetail`, `DocumentChunk`, `AnalysisJob`.
- `ConceptSummary`, `ConceptDetail`, `ConceptRelation`.
- `GraphSnapshot`, `GraphNode`, `GraphEdge`.
- `QuestionResult`, `QuestionSource`, `QuestionHistorySummary`.

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
| `graph.snapshot(filters)` | document ready/delete, concept edit |
| `concepts.detail(id)` | analysis complete, concept edit |
| `questions.list(filters)` | question complete/rerun/delete |
| `questions.detail(id)` | question complete |

### Mutation 규칙

- upload/paste success 202 후 해당 document detail/job을 polling 또는 SSE 구독.
- analysis completed → documents list/detail + graph snapshot invalidate.
- delete 202 → 즉시 graph/list에서 optimistic hide, 실패 시 rollback + error.
- question complete → result panel open + history list invalidate.
- rerun → 기존 result 유지, 새 result를 active로 교체.

질문 POST가 `202`와 `status=queued/retrieving/generating`을 반환하면 `QuestionResultPanel`은 `GET /questions/{id}`를 짧은 간격으로 polling한다. `completed/no_evidence/failed`에서 polling을 종료하고, 입력값과 기존 기록은 보존한다.

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

`KnowledgeGraph`는 `react-force-graph-3d` adapter다. domain graph type을 library node/link type과 직접 섞지 않는다.

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

`QuestionResultPanel` render 순서:

1. question header/status.
2. answer markdown.
3. citation marker links.
4. source cards 1~3.
5. related concepts.
6. retry/edit question actions.

답변은 raw HTML을 허용하지 않고 markdown safe renderer를 사용한다. citation key가 source에 없는 경우 plain text로 노출하지 않고 validation error state로 보여준다.

`SourceCard`:

- `openable=true`: 원문 위치로 이동.
- `openable=false`: snapshot만 표시, disabled link와 stale badge.
- same document 여러 source는 document label을 반복하지 않되 rank/citation을 보존할 수 있다.

`QuestionHistoryPanel`:

- list query pagination.
- click → detail query.
- delete는 optimistic remove 후 실패 rollback.
- rerun은 기존 history를 바꾸지 않는다.

## 8. Analysis SSE

`useAnalysisEvents(jobId)`:

- EventSource URL을 API client base와 조합.
- started/progress/preview/completed/failed/canceled를 reducer로 처리.
- preview는 현재 modal state에만 반영하고 server detail cache에 임시 저장하지 않는다.
- completed event에서 document detail/list/graph query를 invalidate한다.
- connection error는 즉시 실패로 단정하지 않고 exponential reconnect 후 REST detail로 최종 상태를 확인한다.
- modal이 닫혀도 hook은 app-level job tracker가 유지할 수 있어야 한다. 최소 MVP에서는 recent document status polling으로 대체 가능.

## 9. Routing / URL 정책

MVP는 single-page layout으로 시작한다. 브라우저 새로고침 복원을 위해 선택 상태를 query string으로 확장할 수 있다.

권장 query:

- `?document=12`
- `?concept=7`
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
- 이미지/3D asset을 추가하지 않는 MVP는 bundle size를 graph library 중심으로 관리한다.

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
- dark contrast, graph panel overlap, reduced motion.
- dense graph, no evidence, processing, stale evidence screenshots.

## 13. Current implementation migration checklist

- [ ] `KnowledgeDocument/SearchResult/GraphNode`를 API DTO 전체 타입으로 교체.
- [ ] `/knowledge/search` form을 제거하고 `/questions` single entry UI로 통합.
- [ ] `getKnowledgeGraph`를 filter/focus graph snapshot query로 확장.
- [ ] graph node를 document-only에서 document/chunk/concept discriminated node로 확장.
- [ ] App.tsx를 AppShell/features/hooks로 분리.
- [ ] `ensureOk`를 공통 envelope/error decoder로 교체.
- [ ] upload를 text paste + file multipart modal로 확장.
- [ ] `busy` 하나로 전체 화면을 잠그는 동작을 feature별 pending으로 교체.
- [ ] SSE analysis preview와 question history panel 추가.
