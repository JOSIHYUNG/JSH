# 04. Backend Architecture

- 문서 상태: Reviewed / target architecture with runtime mapping
- 기준 문서: `docs/PRD.md`, `docs/01_database_model.md`, `docs/02_api_spec.md`, `docs/external/openai.md`
- runtime: Python 3.12, FastAPI, SQLModel, Alembic
- 목표: 단일 로컬 프로세스에서 단순하게 시작하되, provider·저장소·분석 workflow를 교체 가능한 경계로 분리한다.

## 1. 책임 경계

```text
HTTP/API
  ↓ request schema / error mapping
Application services
  ├─ document ingestion
  ├─ analysis workflow
  ├─ graph query
  ├─ question/retrieval/answer
  └─ history/deletion
  ↓ repositories + ports
Persistence: SQLite/SQLModel/FTS5     Integrations: local FS/OpenAI
```

원칙:

- route는 validation·dependency injection·HTTP response 변환만 담당한다.
- service는 workflow와 transaction 경계를 담당한다.
- repository는 SQLAlchemy/SQLModel query를 캡슐화하고 domain service에 ORM model을 새지 않게 한다.
- OpenAI·filesystem은 port/interface 뒤에 둔다.
- background job은 DB 상태를 source of truth로 사용한다. in-memory queue는 wake-up/진행 이벤트 용도일 뿐이다.
- domain 규칙은 provider response나 UI 상태명에 직접 의존하지 않는다.

## 2. 권장 파일 구조

```text
backend/
├─ app/
│  ├─ main.py
│  ├─ api/
│  │  ├─ __init__.py
│  │  ├─ dependencies.py
│  │  ├─ router.py
│  │  ├─ errors.py
│  │  ├─ response.py
│  │  └─ routes/
│  │     ├─ health.py
│  │     ├─ system.py
│  │     ├─ documents.py
│  │     ├─ concepts.py
│  │     ├─ questions.py
│  │     └─ graph.py
│  ├─ core/
│  │  ├─ config.py
│  │  ├─ logging.py
│  │  ├─ clock.py
│  │  ├─ ids.py
│  │  └─ enums.py
│  ├─ db/
│  │  ├─ session.py
│  │  ├─ pragmas.py
│  │  ├─ transaction.py
│  │  └─ repositories/
│  │     ├─ documents.py
│  │     ├─ chunks.py
│  │     ├─ concepts.py
│  │     ├─ questions.py
│  │     ├─ jobs.py
│  │     └─ graph.py
│  ├─ models/
│  │  ├─ document.py
│  │  ├─ chunk.py
│  │  ├─ keyword.py
│  │  ├─ concept.py
│  │  ├─ relation.py
│  │  ├─ job.py
│  │  └─ question.py
│  ├─ schemas/
│  │  ├─ common.py
│  │  ├─ documents.py
│  │  ├─ concepts.py
│  │  ├─ graph.py
│  │  ├─ questions.py
│  │  └─ jobs.py
│  ├─ services/
│  │  ├─ documents.py
│  │  ├─ ingestion.py
│  │  ├─ analysis.py
│  │  ├─ chunking.py
│  │  ├─ concepts.py
│  │  ├─ graph.py
│  │  ├─ retrieval.py
│  │  ├─ questions.py
│  │  ├─ history.py
│  │  └─ deletion.py
│  ├─ jobs/
│  │  ├─ runner.py
│  │  ├─ registry.py
│  │  ├─ recovery.py
│  │  └─ events.py
│  ├─ integrations/
│  │  ├─ openai/
│  │  │  ├─ client.py
│  │  │  ├─ vector_store.py
│  │  │  ├─ responses.py
│  │  │  ├─ schemas.py
│  │  │  └─ errors.py
│  │  └─ filesystem/
│  │     ├─ storage.py
│  │     └─ validation.py
│  └─ prompts/
│     ├─ document_analysis.py
│     ├─ concept_extraction.py
│     └─ grounded_answer.py
├─ alembic/
│  ├─ env.py
│  └─ versions/
├─ tests/
│  ├─ unit/
│  ├─ integration/
│  ├─ api/
│  ├─ fixtures/
│  └─ conftest.py
└─ data/
```

현재 구현은 `app/db.py`, `app/api/routes/knowledge_v1.py`, `app/services/{documents,analysis,graph,questions,retrieval,jobs,read_models}.py`로 구성된다. 이 문서는 목표 모듈 경계를 설명하며 현재 차이는 아래에 기록한다.

### Runtime mapping

| 목표 경계 | 현재 구현 | 판정 |
|---|---|---|
| resource routes | `knowledge_v1.py` | 단일 resource router. 기능 증가 시 route module 분리 |
| repositories | 일부 service 내부 SQLModel query | MVP 허용. query 복잡도 증가 시 분리 |
| durable analysis | `AnalysisWorkflow` + `BackgroundTasks` + `analysis_jobs` | DB 상태는 durable하며 재시작 시 중단 job을 실패 처리해 복구 가능 상태로 전환 |
| OpenAI ports | `integrations/openai/{client,responses,vector_store}.py` | provider 호출 경계 준수 |
| SSE | `/documents/{id}/analysis/events` | 현재 상태 replay, 변경 progress, event ID, heartbeat, terminal event 구현 |
| response envelope | `app/core/envelope.py` | 구현됨. 204 delete만 body 없음 |

## 3. Layer별 규칙

### 3.1 API layer

책임:

- path/query/body/form validation.
- DB session과 current settings dependency 주입.
- service 호출과 HTTP status 결정.
- domain exception을 공통 error envelope으로 매핑.
- SSE response 생성과 disconnect 처리.

금지:

- ORM query를 route 함수에 직접 작성.
- OpenAI SDK 호출.
- `json.loads(keywords_json)` 같은 persistence detail을 schema 변환에서 수행.
- raw exception text를 사용자 응답으로 반환.

### 3.2 Application service

service는 use case 하나를 중심으로 만든다.

| service | use case |
|---|---|
| `DocumentService` | paste/upload 등록, 목록, detail, reanalyze request |
| `IngestionService` | temp asset 검증, hash, title 제안, draft 생성 |
| `AnalysisWorkflow` | 단계별 AI 분석·chunk·concept·relation·commit |
| `GraphService` | filters/focus/limits로 graph read model 생성 |
| `RetrievalService` | FTS 보정 + Vector Store search + local mapping |
| `ConversationContextService` | 완료 turn 조회, context window/절단, standalone query context |
| `QuestionService` | conversation turn 생성, grounded answer, source snapshot |
| `HistoryService` | 대화/turn 목록·상세·재실행·삭제 |
| `DeletionService` | hide → external delete → local cleanup |

service 메서드는 request schema가 아니라 domain input을 받는 것을 원칙으로 한다. HTTP pagination/filter parsing은 route 또는 query object가 담당한다.

### 3.3 Repository

- 한 repository는 한 aggregate의 조회·저장 정책을 소유한다.
- `Session`은 dependency로 주입하며 repository가 새 session을 만들지 않는다.
- list query는 명시적인 `order_by`를 항상 가진다.
- `selectinload` 등 관계 preload를 repository 안에서 결정한다.
- count query와 page query를 분리해 pagination을 만든다.
- FTS는 `ChunkRepository.search_lexical()`에서만 호출한다.

### 3.4 Integration port

필수 port:

| port | 구현 |
|---|---|
| `OriginalStorage` | `LocalFileStorage` |
| `VectorStoreGateway` | `OpenAIVectorStoreGateway` |
| `AnswerModelGateway` | `OpenAIResponsesGateway` |
| `Clock` | UTC system/fake clock |

`OriginalStorage`는 `put`, `delete`, `exists`, `read_range`, `hash` 연산만 노출한다. 원문 전체를 API route에서 직접 file handle로 다루지 않으며, `read_range`가 API의 원문 위치 강조 계약을 구현한다.

unit test에서는 fake 구현을 사용한다. SDK response 타입을 service에 그대로 전달하지 않고 provider DTO로 변환한다.

## 4. Configuration

`pydantic-settings`로 읽고 startup 때 validate한다.

| 환경변수 | 기본/필수 | 설명 |
|---|---|---|
| `APP_ENV` | `development` | 환경 |
| `APP_VERSION` | package version | health 반환 |
| `DATABASE_URL` | `sqlite:///./data/app.db` | SQLite URL |
| `STORAGE_ROOT` | `./data/storage` | local file root |
| `OPENAI_API_KEY` | 선택 | 미설정 시 AI 단계는 명확한 degraded 상태 |
| `OPENAI_VECTOR_STORE_ID` | 선택 | 단일 Vector Store. 없으면 필요 시 생성 여부 설정 |
| `OPENAI_CHAT_MODEL` | `gpt-5.6-terra` | Responses 분석·답변 모델. 환경변수로 교체 |
| `OPENAI_TIMEOUT_SECONDS` | 60 | 개별 OpenAI 요청 timeout |
| `MAX_UPLOAD_BYTES` | 20 MB 권장 | 애플리케이션 제한 |
| `CORS_ORIGINS` | local frontend origin | allowlist |
| `ANALYSIS_TIMEOUT_SECONDS` | 300 | 외부 작업 timeout |
| `QUESTION_TIMEOUT_SECONDS` | 90 | 질문 timeout |
| `GRAPH_NODE_LIMIT` | 500 | graph 기본 limit |

- API key는 settings object에서만 접근하고 로그·응답·DB에 기록하지 않는다.
- environment가 바뀌어도 API schema는 바뀌지 않는다.
- startup에서 storage directory, SQLite connection, Alembic version, Vector Store configured 상태를 확인한다.

## 5. Startup / shutdown

### Startup 순서

1. logging·request ID middleware 구성.
2. settings load 및 안전한 validation.
3. storage root 생성/권한 확인.
4. SQLite engine 생성, WAL/foreign key/busy timeout PRAGMA 설정.
5. migration version 확인. 앱이 자동으로 migration을 실행하지 않는 운영 모드도 지원하되 개발 실행 명령은 `alembic upgrade head`로 고정한다.
6. `queued/running/cancel_requested` job recovery scan. 기존 결과가 있으면 문서는 `ready`, 없으면 `failed`로 복구하고 job에 `SERVICE_RESTARTED`를 기록한다.
7. in-process background task 실행 준비.
8. routers mount.

### Shutdown 순서

1. 신규 job 수락 중지.
2. in-flight task에 graceful cancellation 신호.
3. 현재 DB 상태 commit.
4. OpenAI client/session 및 engine dispose.

## 6. 분석 workflow

분석은 `AnalysisWorkflow.run(job_id)` 하나의 orchestration에서 수행한다. 각 단계는 재시도 가능한 함수로 분리한다.

### 6.1 단계

| 단계 | 작업 | 저장/이벤트 |
|---|---|---|
| received | request와 원문 검증 | draft, progress 0 |
| stored | temp → final asset, hash | storage key |
| chunking | 24,000/500 chunk | chunks + FTS |
| summarizing | title/summary/keywords structured output | document fields |
| extracting_concepts | chunk별 concepts/aliases | concepts + aliases + association |
| linking_concepts | explicit relations, merge candidates | relations |
| finalizing | chunks/FTS/keywords/concepts/relations 원자적 교체 | document `ready`, job `completed` |
| vector_store_uploading | 전체 원문 upload·index poll | document vector status `uploading` → `indexed` 또는 `failed` |

로컬 분석과 그래프·FTS 적재가 완료되면 문서와 job을 먼저 완료 처리한다. Vector Store 동기화는 그 뒤의 best-effort 단계이며, 실패해도 로컬 문서의 `ready` 상태를 되돌리지 않는다. 각 단계 완료 때 job row를 commit한다. SSE는 DB 상태를 source of truth로 읽으므로 연결이 끊겨도 재접속 또는 polling으로 복구한다.

### 6.2 AI 분석 정책

- 전체 원문은 로컬 분석 성공 후 Vector Store에 전달한다.
- 내부 graph/evidence chunk는 독립적으로 분석하되, output이 과도하면 chunk를 의미 단위로 나누어 여러 호출한다. 고정된 concept hard cap은 두지 않는다.
- structured output schema는 `DocumentAnalysis`, `ChunkConceptExtraction`, `ChunkRelationExtraction`로 분리한다.
- concept description은 짧게, canonical/English/abbreviation을 명시적으로 요구한다.
- 모델 output schema 검증 실패는 해당 단계 retry 후 `ANALYSIS_OUTPUT_INVALID`로 종료한다.
- API key가 구성된 환경에서 Responses 분석이 실패하면 단순 키워드 fallback으로 성공한 것처럼 처리하지 않고 원문을 보존한 채 `failed`로 전환한다.
- API key가 없는 로컬 모드에서만 제한된 결정적 fallback 분석을 허용하며, system status에서 AI 미연결을 명확히 표시한다.

구조화 출력 계약:

| 출력 단위 | 필드 | 제한/규칙 |
|---|---|---|
| `DocumentAnalysis` | `title`, `summary`, `keywords[]` | title 255자, summary 1,000자, keyword 3~20개 |
| `ChunkConceptExtraction` | `chunk_index`, `concepts[]` | concept hard cap 없음; 설명 160자 이내 |
| concept item | `concept_type`, `canonical_name`, `english_name`, `abbreviation`, `description`, `mention`, `mention_start`, `mention_end`, `confidence` | 13개 enum 중 하나; 위치는 chunk 기준 |
| `ChunkRelationExtraction` | `chunk_index`, `relations[]` | `source_mention`, `target_mention`, `relation_type`, `explanation`, `confidence` |

concept extraction 결과는 chunk별로 독립 처리하고, merge/alias 판단은 model output을 그대로 신뢰하지 않고 `ConceptService`가 정규화 규칙으로 재검증한다. relation의 source/target이 concepts에 매핑되지 않으면 저장하지 않는다. 제외 수 집계는 P1 품질 관측 항목이다.

### 6.3 commit strategy

- 분석 결과를 기존 active result와 동일 transaction에서 섞지 않는다.
- MVP는 새 결과를 workflow context에 모은 뒤 final transaction에서 active 결과를 교체한다. 단계별 DB commit은 job 상태·progress·provider ID만 대상으로 한다.
- 분석 결과를 DB에 부분 저장하지 않으므로 실패 시 orphan chunk/concept를 정리할 필요가 없다. 원문과 job만 `failed`로 남긴다.
- final transaction에서 chunks/FTS/keywords/concepts/relations, document status, counts, job status를 함께 변경한다.
- 동일 원문 재분석 실패 시 기존 chunk가 현재 원문과 정확히 일치하면 기존 `ready` 결과를 유지한다. 원문 수정 후 분석 실패처럼 기존 chunk가 현재 asset과 불일치하면 `failed`로 두어 오래된 근거를 노출하지 않는다.
- `title_source=user`인 제목은 분석 결과로 덮어쓰지 않는다.

## 7. Vector Store / Responses 연동

### 7.1 책임 분리

- `VectorStoreGateway`: file upload, poll indexing, search, delete, provider error normalization.
- `ResponsesGateway`: structured document analysis, grounded answer, output validation.
- `RetrievalService`: provider 결과를 local chunk로 mapping하고 top 3을 결정.
- `QuestionService`: local evidence만 model context로 전달하고 citations를 검증.

### 7.2 Retrieval mapping

Vector Store가 반환한 `file_id/content/score`를 다음 순서로 local chunk와 매핑한다.

1. file ID로 document를 찾는다.
2. normalized content가 local chunk content에 exact substring인지 확인한다.
3. exact match가 없으면 normalized n-gram overlap과 offset proximity로 best chunk를 선택한다.
4. mapping confidence가 threshold 미만이면 source에 `mapping_unavailable`를 기록하고 답변 context에서 제외한다.
5. local chunk 최대 3개를 rank로 고정하고 document link는 중복 제거한다.

검색 후보 선택:

- Vector Store가 정상이고 indexed local file mapping이 있으면 semantic 결과를 우선한다.
- Vector Store가 비활성·실패했거나 mapping 가능한 결과가 없으면 FTS5를 실행하고 `retrieval_provider=lexical_fallback`으로 기록한다.
- 현재 MVP는 두 provider의 점수를 혼합하지 않는다. 추후 혼합 검색을 도입하면 score calibration과 회귀 평가를 먼저 정의한다.
- 관련도 threshold 미만 후보는 3개를 채우기 위해 추가하지 않는다.

이 매핑이 있어야 답변 citation이 application의 `/documents/{id}`와 chunk 위치로 이동할 수 있다. provider citation을 그대로 사용자 link로 사용하지 않는다.

### 7.3 Grounded answer

- prompt에는 question, `S1..S3` evidence content, source metadata만 전달한다.
- 답변은 근거에 없는 사실을 만들지 않고, citation key를 문장 끝에 붙인다.
- 구조화 결과는 `answer_markdown`, `used_citations`, `insufficient_evidence`로 받고, `used_citations`가 실제 source rank subset인지 검증한다.
- 검증 실패 시 답변을 사용자에게 노출하지 않고 한 번 재시도한다. 계속 실패하면 근거 카드만 보여주고 오류/부족 상태로 종료한다.

## 8. Question workflow

```text
POST /conversations/{id}/questions or POST /questions
  → validate question and conversation
  → create question_history turn(queued)
  → assemble recent completed context (max 6 + budget)
  → rewrite follow-up to standalone retrieval query
  → retrieval (Vector Store + lexical fallback)
  → map to local chunks
  → no evidence? no_evidence
  → Responses grounded answer with history context + current evidence
  → validate current-turn citations
  → save source snapshots + completed
  → update conversation metadata
  → return ChatTurn/QuestionResult
```

`QuestionHistory`는 기존 단일 질문 기록과 호환되는 chat turn이다. 기존 row는 migration에서 개별 conversation의 첫 turn으로 backfill한다. 이전 turn은 답변 맥락일 뿐 citation 근거가 아니며, 매 turn의 `S1..S3`만 답변 citation으로 허용한다. API는 질문 row를 먼저 `queued`로 저장하고 오래 걸리는 경우 `202 + GET polling`을 사용한다.

질문에 외부 AI가 연결되지 않아도 원문/DB와 검색된 근거 snapshot은 보존한다. configured false이면 질문 상태를 `failed`, 오류를 `AI_NOT_CONFIGURED`로 기록하고 생성 답변은 반환하지 않는다. Responses 호출 또는 citation 검증 실패도 같은 방식으로 근거 카드는 보존하되 가짜 답변을 노출하지 않는다.

## 9. Graph query

GraphService는 다음 파생 규칙을 사용한다.

- document node: ready document.
- chunk node: `include_chunks=true` 또는 focus document의 expanded chunk.
- concept node: visible concept이며 source chunk가 ready document에 속함.
- document→chunk edge: `contains`.
- chunk→concept edge: `mentions`, association의 extraction confidence를 strength로 사용.
- concept→concept edge: relation row, relation type/direction/strength/evidence 포함.
- 문서·개념의 direct link는 query response에서 필요하면 `document → concept` derived edge로 만들되, source는 실제 chunk로 남긴다.

GraphService는 전체 pairwise concept 비교를 매 request에 하지 않는다. edge는 DB에 저장된 relation과 association에서만 조합한다. 데이터가 없는 초기 legacy graph의 semantic pairwise 계산은 migration/backfill command의 일회성 작업이다.

## 10. Error handling

### Domain exception hierarchy

| exception | API code |
|---|---|
| `ValidationDomainError` | `INVALID_INPUT` |
| `NotFoundDomainError` | resource-specific 404 |
| `ConflictDomainError` | `DUPLICATE_DOCUMENT`/`DOCUMENT_BUSY` |
| `ProviderUnavailableError` | `OPENAI_UNAVAILABLE` |
| `ProviderNotReadyError` | `VECTOR_STORE_NOT_READY` |
| `StorageError` | `SERVICE_NOT_READY` 또는 `INTERNAL_ERROR` |
| `WorkflowOutputError` | `ANALYSIS_OUTPUT_INVALID` |

global exception handler는:

- request_id를 error meta에 넣는다.
- stack trace는 server log에만 남긴다.
- 사용자 message는 한국어 action-oriented 문구를 사용한다.
- retryable과 suggested action을 details에 넣는다.

### 외부 장애 정책

- 429: retry-after가 있으면 job backoff에 반영.
- timeout: 제한 횟수 내 exponential backoff.
- 4xx validation: 자동 retry 금지, job failed.
- Vector Store indexing 지연: SDK poll helper로 대기하되, timeout/실패는 document vector status에만 기록하고 로컬 준비 상태는 유지.
- Responses output schema 오류: 동일 입력 1회 retry, 이후 failed.

## 11. Observability

로그 필수 필드:

- `timestamp`, `level`, `request_id`, `job_id`, `document_id`, `question_id`.
- event name, duration_ms, result status, error code.
- model 이름·token usage는 secret 없이 provider usage field만 저장/로그.

로그 금지:

- API key, 원문 전문, 질문 전문, 답변 전문, provider raw payload.

운영 지표:

- upload → ready duration.
- vector indexing duration/error.
- analysis stage duration/failure.
- retrieval mapping confidence distribution.
- question no-evidence rate, citation validation failure, answer latency.
- graph node/edge count and truncation rate.

## 12. 테스트 전략

### Unit

- chunk boundary/offset/overlap.
- filename/path/hash validation.
- concept normalization/merge candidate.
- relation deduplication.
- retrieval score normalization and local mapping.
- citation validation.
- API error mapping.

### Integration

- SQLite migration from empty/current DB.
- FTS insert/update/delete consistency.
- full document workflow with fake OpenAI gateway.
- failure at each analysis stage leaves recoverable document/job.
- deletion hides document before external delete and preserves question snapshot.

### API

- every endpoint envelope, status code, pagination/filter.
- multipart upload limits and unsupported types.
- SSE reconnect/current state.
- question result source/citation contract.

### Contract

OpenAPI generated by FastAPI is checked against frontend `api` types for:

- enum values.
- nullable fields.
- date/number representation.
- error envelope.
- graph node/edge discriminators.

## 13. Current implementation migration checklist

2026-07-30 역검증 결과:

- [x] 원문 local asset 저장과 normalized chunk/concept/relation 테이블 사용.
- [x] Vector Store gateway와 Responses Structured Outputs를 integration 경계로 분리.
- [x] document/chunk/concept graph snapshot API 구현.
- [x] `/documents`, `/questions`, `/graph` resource API와 표준 envelope 구현.
- [x] 분석 job DB 상태와 SSE progress stream 구현.
- [x] `AI에게 질문` 단일 entry와 최대 3개 local evidence mapping 구현.
- [x] conversation/turn 저장, 최근 context window, standalone retrieval query를 구현한다.
- [x] turn별 source snapshot을 유지하는 멀티턴 API와 대화 목록/상세를 구현한다.
- [x] 질문 처리를 `202 + GET polling` 상태 계약으로 통일한다.
- [x] SSE heartbeat, event ID, terminal event와 frontend polling fallback을 구현.
- [x] 요청 ID 전파, validation 입력값 비노출, 원문·질문 응답 `no-store`를 구현.
- [x] pytest가 운영 DB를 건드리지 않도록 임시 DB·storage와 Alembic head fixture를 구현.
- [ ] route 내부 SQLModel query를 repository 계층으로 점진적으로 이동한다. (P1 유지보수)
- [ ] `BackgroundTasks`를 별도 durable worker로 교체해 프로세스 종료 후 자동 재시도를 지원한다. (P4)
- [ ] 질문 비동기 처리가 필요한 문서 규모에서 queue/worker 경계를 추가한다. (P4 이후)
