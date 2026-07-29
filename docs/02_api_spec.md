# 02. API Specification

- 문서 상태: Draft / Architecture baseline
- 기준 문서: `docs/PRD.md`, `docs/01_database_model.md`
- Base URL: `/api/v1`
- Transport: JSON over HTTP; 분석 진행은 Server-Sent Events
- 인증: MVP에서는 없음. 서버가 실행 중인 로컬 환경을 단일 사용자 경계로 취급한다.

## 1. API 원칙

1. 모든 응답은 성공·실패를 동일한 envelope으로 감싼다.
2. 모든 request에는 서버가 생성한 `request_id`가 응답과 로그에 연결된다.
3. 사용자에게 노출되는 AI 진입점은 `POST /questions` 하나다. 별도 public search endpoint는 만들지 않는다.
4. 목록은 동일한 pagination·filter 규칙을 사용한다.
5. 분석·삭제·재분석은 비동기 작업/상태를 반환한다. `202 Accepted`와 resource status를 사용한다.
6. HTTP status만 읽어도 큰 분류가 가능하고, 상세 처리는 stable `error.code`로 한다.
7. API는 DB model을 그대로 반환하지 않는다. 응답 schema는 API용 read model이다.

## 2. 공통 계약

### 2.1 Success envelope

| 필드 | 타입 | 필수 | 설명 |
|---|---|---:|---|
| `data` | object / array / null | Y | 실제 payload |
| `meta` | object | Y | request·pagination·trace 정보 |
| `meta.request_id` | string | Y | 서버 요청 ID |
| `meta.generated_at` | string | Y | 응답 생성 UTC 시각 |
| `meta.pagination` | object | N | 목록 endpoint에서만 사용 |
| `meta.warnings` | array | N | 부분 결과·외부 서비스 지연 경고 |
| `error` | null | Y | 성공 시 null |

### 2.2 Error envelope

| 필드 | 타입 | 설명 |
|---|---|---|
| `data` | null | 항상 null |
| `meta.request_id` | string | 문의·로그 추적용 |
| `meta.generated_at` | string | UTC |
| `error.code` | string | 변경하지 않는 기계 판별 코드 |
| `error.message` | string | 사용자에게 보여줄 한국어 기본 메시지 |
| `error.details` | object | field error, limit, 상태 등 안전한 추가 정보 |
| `error.retryable` | boolean | 자동/수동 재시도 가능 여부 |

### 2.3 Pagination

offset 기반 MVP를 사용한다. SQLite 단일 사용자 규모에서 예측 가능하고, 프론트의 페이지 이동·기록 목록 처리에 단순하다.

| query | 타입 | 기본 | 제한 | 설명 |
|---|---|---:|---:|---|
| `page` | integer | 1 | >= 1 | 1-based |
| `page_size` | integer | 20 | 1~100 | 서버가 100 초과를 100으로 clamp하지 않고 422로 거부 |
| `sort` | enum | `created_at` | endpoint별 허용값 | 허용되지 않은 값은 422 |
| `order` | enum | `desc` | `asc/desc` | 정렬 방향 |

`meta.pagination`:

| 필드 | 타입 | 설명 |
|---|---|---|
| `page` | integer | 현재 페이지 |
| `page_size` | integer | 적용된 크기 |
| `total_items` | integer | 전체 항목 수 |
| `total_pages` | integer | 전체 페이지 수 |
| `has_next` | boolean | 다음 페이지 존재 |
| `has_previous` | boolean | 이전 페이지 존재 |

목록 `data`는 `{ "items": [...] }` 형태로 통일한다.

### 2.4 날짜·ID·문자열

- ID는 JSON number인 양의 정수다.
- 날짜는 `2026-07-29T12:34:56.123456Z` 형식이다.
- 질문·문서 본문은 서버에서 trim하고, 빈 문자열을 거부한다.
- `title` 최대 255자, `question` 2~1,000자, `summary` 최대 1,000자, preview는 최대 500자다.
- API가 반환하는 markdown 답변은 raw HTML을 포함하지 않는다.

## 3. 공통 error code

| HTTP | code | 의미 | retryable |
|---:|---|---|---:|
| 400 | `INVALID_INPUT` | 값 형식·범위·빈 입력 오류 | N |
| 400 | `UNSUPPORTED_FILE_TYPE` | 허용하지 않은 파일 형식 | N |
| 400 | `FILE_EMPTY` | 읽을 텍스트가 없음 | N |
| 404 | `DOCUMENT_NOT_FOUND` | 문서가 없음/이미 숨김 | N |
| 404 | `CONCEPT_NOT_FOUND` | 개념이 없음 | N |
| 404 | `QUESTION_NOT_FOUND` | 질문 기록이 없음 | N |
| 404 | `DOCUMENT_SOURCE_UNAVAILABLE` | 원문 asset이 없음/삭제 중 | N |
| 409 | `DUPLICATE_DOCUMENT` | 동일 원문이 이미 존재 | N |
| 409 | `DOCUMENT_BUSY` | 분석·삭제 작업 중 | Y |
| 409 | `ANALYSIS_NOT_CANCELABLE` | 완료/취소된 작업 | N |
| 422 | `VALIDATION_ERROR` | Pydantic schema 검증 실패 | N |
| 422 | `ANALYSIS_OUTPUT_INVALID` | AI 구조화 결과 검증 실패 | Y |
| 500 | `INTERNAL_ERROR` | 예상하지 못한 서버 오류 | Y |
| 502 | `OPENAI_UNAVAILABLE` | OpenAI API 연결/응답 실패 | Y |
| 502 | `VECTOR_STORE_NOT_READY` | Vector Store indexing 실패/지연 | Y |
| 503 | `AI_NOT_CONFIGURED` | API key 또는 Vector Store 설정 없음 | N |
| 503 | `SERVICE_NOT_READY` | DB·파일 저장소·설정 초기화 실패 | Y |

field validation은 `error.details.fields` 배열의 `{field, reason, value}`로 반환한다. `value`에는 API key·원문 전체·민감한 내용을 넣지 않는다.

## 4. DTO 정의

### 4.1 DocumentSummary

| 필드 | 타입 | 필수 | 설명 |
|---|---|---:|---|
| `id` | integer | Y | 문서 ID |
| `title` | string | Y | 대표 제목 |
| `filename` | string or null | Y | 파일명 또는 null |
| `source_type` | enum | Y | `paste/upload` |
| `media_type` | string | Y | MIME |
| `summary` | string | Y | 짧은 요약 |
| `keywords` | string[] | Y | 우선순위 순 |
| `status` | enum | Y | `draft/processing/ready/failed/deleting` |
| `character_count` | integer | Y | 정규화 원문 길이 |
| `chunk_count` | integer | Y | 청크 수 |
| `concept_count` | integer | Y | 연결된 개념 수 |
| `created_at` | datetime | Y | 생성 시각 |
| `updated_at` | datetime | Y | 변경 시각 |

### 4.2 DocumentChunk

| 필드 | 타입 | 필수 | 설명 |
|---|---|---:|---|
| `id` | integer | Y | 청크 ID |
| `document_id` | integer | Y | 문서 ID |
| `chunk_index` | integer | Y | 0부터 시작 |
| `content` | string | Y | 상세 조회 시 전체, 목록에서는 preview |
| `preview` | string | Y | 최대 500자 |
| `start_char` | integer | Y | 원문 offset |
| `end_char` | integer | Y | exclusive offset |
| `concept_ids` | integer[] | Y | 청크에서 발견된 개념 |

### 4.3 ConceptSummary / ConceptDetail

`ConceptSummary`는 `id`, `concept_type`, `canonical_name`, `english_name`, `abbreviation`, `description`, `document_count`, `chunk_count`, `visibility`를 갖는다.

`ConceptDetail`은 summary에 다음을 추가한다.

- `aliases`: `{alias, alias_type, source_chunk_id, confidence}[]`
- `source_chunks`: `ChunkEvidence[]`
- `related_concepts`: `{concept, relation_type, strength, evidence_chunk_id, explanation}[]`

### 4.4 GraphSnapshot

| 필드 | 타입 | 설명 |
|---|---|---|
| `nodes` | GraphNode[] | 문서·청크·개념 노드 |
| `edges` | GraphEdge[] | 문서→청크·청크→개념·개념→개념 |
| `filters` | object | 서버가 실제 적용한 filter |
| `truncated` | boolean | limit으로 일부 생략되었는지 |
| `node_count` | integer | 반환 노드 수 |
| `edge_count` | integer | 반환 엣지 수 |

`GraphNode`:

| 필드 | 타입 | 설명 |
|---|---|---|
| `id` | string | `document:1`, `chunk:2`, `concept:3` |
| `entity_type` | enum | `document/chunk/concept` |
| `entity_id` | integer | 원본 ID |
| `label` | string | 그래프 표시명 |
| `subtype` | string or null | concept type 또는 null |
| `size` | number | 연결도 기반 시각 크기 힌트 |
| `color_token` | string | 디자인 시스템 semantic token |
| `metadata` | object | title, summary, count 등 최소 정보 |

`GraphEdge`:

| 필드 | 타입 | 설명 |
|---|---|---|
| `id` | string | 안정적인 edge key |
| `source` | string | GraphNode.id |
| `target` | string | GraphNode.id |
| `edge_type` | enum | `contains/mentions/relates` |
| `relation_type` | string or null | 개념 관계명 |
| `strength` | number | 0~1 |
| `is_directed` | boolean | 방향성 |
| `evidence_chunk_id` | integer or null | 출처 |

### 4.5 QuestionResult

| 필드 | 타입 | 설명 |
|---|---|---|
| `id` | integer | 질문 기록 ID |
| `question` | string | 원 질문 |
| `status` | enum | `queued/retrieving/generating/completed/no_evidence/failed` |
| `answer_markdown` | string or null | 근거 기반 답변 |
| `answer_language` | string or null | `ko`, `en` 등 |
| `sources` | QuestionSource[] | 실제 사용 근거 0~3개 |
| `related_concepts` | ConceptSummary[] | 질문·근거에서 연결된 개념 |
| `retrieval` | object | count, scores, mapping status |
| `created_at` | datetime | 실행 시각 |
| `completed_at` | datetime or null | 완료 시각 |

`QuestionSource`:

| 필드 | 타입 | 설명 |
|---|---|---|
| `rank` | integer | 1~3 |
| `citation_key` | string | `S1`~`S3` |
| `document_id` | integer or null | 현재 문서 ID |
| `chunk_id` | integer or null | 현재 청크 ID |
| `document_title` | string | 현재값 또는 snapshot |
| `document_status` | string | `ready/deleted/reanalyzed` |
| `chunk_preview` | string | 당시 근거 preview |
| `start_char` | integer or null | 현재 이동 가능할 때 |
| `end_char` | integer or null | 현재 이동 가능할 때 |
| `score` | number | 0~1 또는 provider score normalized |
| `mapping_confidence` | number | 외부 결과→local chunk 매핑 신뢰도 |
| `openable` | boolean | 원문 위치 이동 가능 여부 |

`retrieval`:

| 필드 | 타입 | 설명 |
|---|---|---|
| `provider` | enum | `vector_store`, `lexical_fallback`, `none` |
| `candidate_count` | integer | provider가 반환한 후보 수 |
| `returned_count` | integer | local mapping 후 답변에 사용한 수 |
| `mapping_failures` | integer | local chunk로 연결하지 못한 후보 수 |
| `top_score` | number or null | 선택된 최고 score |
| `used_chunk_ids` | integer[] | 답변 context에 실제 사용한 청크 |

## 5. Endpoint 목록

| Method | Path | 목적 | 성공 |
|---|---|---|---:|
| GET | `/health` | liveness/readiness | 200 |
| GET | `/system/status` | DB·파일·AI 구성 상태 | 200 |
| GET | `/documents` | 문서 목록 | 200 |
| POST | `/documents` | 붙여넣기 자료 등록/분석 시작 | 202 |
| POST | `/documents/upload` | 텍스트 파일 등록/분석 시작 | 202 |
| GET | `/documents/{document_id}` | 문서 상세 | 200 |
| DELETE | `/documents/{document_id}` | 문서 삭제 시작 | 202 |
| POST | `/documents/{document_id}/reanalyze` | 재분석 시작 | 202 |
| GET | `/documents/{document_id}/analysis/events` | 분석 SSE | 200 stream |
| POST | `/documents/{document_id}/analysis/cancel` | 분석 취소 요청 | 202 |
| GET | `/documents/{document_id}/chunks/{chunk_id}` | 청크 상세 | 200 |
| GET | `/documents/{document_id}/original` | 원문 구간 조회 | 200 |
| GET | `/concepts/{concept_id}` | 개념 상세 | 200 |
| POST | `/questions` | 유일한 사용자 질문 진입점 | 201/202 |
| GET | `/questions` | 질문 기록 목록 | 200 |
| GET | `/questions/{question_id}` | 질문 기록 상세 | 200 |
| POST | `/questions/{question_id}/rerun` | 질문 재실행 | 202 |
| DELETE | `/questions/{question_id}` | 질문 기록 삭제 | 204 |
| GET | `/graph` | 그래프 snapshot | 200 |

## 6. System

### GET `/health`

용도: reverse proxy와 개발 서버의 liveness 확인. 외부 API 호출은 하지 않는다.

Response `data`:

| 필드 | 타입 | 설명 |
|---|---|---|
| `status` | string | 항상 `ok` |
| `service` | string | `jsh-backend` |
| `version` | string | 앱 버전 |

### GET `/system/status`

Response `data`:

| 필드 | 타입 | 설명 |
|---|---|---|
| `database` | `ready/degraded` | DB 연결/마이그레이션 |
| `file_storage` | `ready/degraded` | root read/write |
| `openai_configured` | boolean | key가 서버에 설정되었는지. key 자체는 절대 반환하지 않음 |
| `vector_store_configured` | boolean | Vector Store ID 준비 여부 |
| `analysis_running` | integer | 활성 job 수 |
| `app_version` | string | 서버 버전 |

## 7. Documents

### GET `/documents`

Query:

| 파라미터 | 타입 | 기본 | 설명 |
|---|---|---:|---|
| `status` | enum[] | all | comma-separated `draft,processing,ready,failed,deleting` |
| `source_type` | enum | all | `paste/upload` |
| `created_from` | date | none | UTC 날짜 이상 |
| `created_to` | date | none | UTC 날짜 이하 |
| `sort` | enum | `created_at` | `created_at/title/updated_at` |
| `order` | enum | desc | asc/desc |
| `page`, `page_size` | integer | 1,20 | pagination |

Response `data.items`: `DocumentSummary[]`.

### POST `/documents`

용도: 모달의 텍스트 입력을 등록한다. 저장은 분석 완료 전에도 draft 원문을 보존한다.

Request body:

| 필드 | 타입 | 필수 | 제한 |
|---|---|---:|---|
| `title` | string or null | N | null이면 첫 유의미한 줄/파일명으로 제안 |
| `content` | string | Y | trim 후 1자 이상 |
| `source_name` | string or null | N | 사용자 표시용 파일명 |
| `auto_analyze` | boolean | N | 기본 true |

처리:

- 중복 hash면 409 `DUPLICATE_DOCUMENT`; details에 기존 document ID를 포함한다.
- 정상 입력은 `documents.status=processing`, `analysis_job`을 만들고 즉시 반환한다.

Response `202 data`:

| 필드 | 타입 |
|---|---|
| `document` | DocumentSummary |
| `job` | AnalysisJob |

### POST `/documents/upload`

Request: `multipart/form-data`.

| part | 타입 | 필수 | 설명 |
|---|---|---:|---|
| `file` | binary | Y | `.txt`, `.md` P0. PDF는 설정으로 허용할 때만 |
| `title` | string | N | 자동 제안 override |
| `auto_analyze` | boolean | N | 기본 true |

헤더/검증:

- 허용 MIME과 확장자를 함께 검사한다.
- 파일 size는 `MAX_UPLOAD_BYTES` 설정을 넘을 수 없다.
- UTF-8 계열 텍스트를 기본 지원한다. binary/empty/압축 파일은 400.
- filename은 path가 아닌 basename으로만 저장한다.

Response와 오류는 `POST /documents`와 동일하다.

### GET `/documents/{document_id}`

Query:

| 파라미터 | 타입 | 기본 | 설명 |
|---|---|---:|---|
| `include_chunks` | boolean | true | 청크 목록 포함 |
| `include_concepts` | boolean | true | 개념 목록 포함 |
| `chunks_page`, `chunks_page_size` | integer | 1,20 | 긴 문서 상세 pagination |

Response `data`:

- `document`: DocumentSummary 확장값
- `chunks`: `DocumentChunk[]`
- `chunks_pagination`: `PaginationMeta`
- `concepts`: ConceptSummary[]
- `latest_job`: AnalysisJob 또는 null
- `source`: `{storage_available, vector_store_status}`

### DELETE `/documents/{document_id}`

Response `202 data`:

| 필드 | 타입 | 설명 |
|---|---|---|
| `document_id` | integer | 대상 |
| `status` | string | `deleting` |
| `message` | string | 사용자 안내 |

삭제 직후 문서는 목록·그래프·질문 retrieval에서 제외한다. 완료 여부는 document detail/status polling으로 확인한다. 이미 deleting/deleted면 409 또는 404로 일관되게 처리한다.

### POST `/documents/{document_id}/reanalyze`

Request body:

| 필드 | 타입 | 필수 | 설명 |
|---|---|---:|---|
| `reason` | string or null | N | audit용 짧은 이유 |
| `force_vector_reindex` | boolean | N | 기본 false. 원문 변경 없으면 기존 file 재사용 |

Response `202`: `document`, `job`.

### GET `/documents/{document_id}/analysis/events`

SSE event types:

| event | data 필드 | 설명 |
|---|---|---|
| `analysis.started` | job_id, document_id, stage, progress | 연결 직후 현재 상태도 replay |
| `analysis.progress` | job_id, stage, progress, message, counts | 단계 진행 |
| `analysis.preview` | job_id, kind, payload | title/summary/concept/relation의 안전한 preview |
| `analysis.completed` | job_id, document_id, document_status | 완료와 최신 document summary |
| `analysis.failed` | job_id, error | retry action 정보 |
| `analysis.canceled` | job_id, document_id | 원문 draft/failed 상태 |
| `heartbeat` | server_time | 15초 idle keepalive |

`analysis.preview.data` 공통 필드:

| 필드 | 타입 | 설명 |
|---|---|---|
| `job_id` | integer | 작업 ID |
| `kind` | enum | `title`, `summary`, `keyword`, `concept`, `relation` |
| `sequence` | integer | job 내 증가 순번 |
| `payload` | object | kind별 안전한 preview |

kind별 payload:

- `title`: `{title}`.
- `summary`: `{summary}`.
- `keyword`: `{keyword, rank}`.
- `concept`: `{concept_type, canonical_name, english_name, abbreviation, description, state}`. `state`는 `new/existing/similar_candidate`.
- `relation`: `{source_name, target_name, relation_type, strength, evidence_chunk_index}`.

preview에는 원문 전체·API key·provider raw response를 넣지 않는다.

클라이언트가 연결을 끊어도 작업은 계속된다. `Last-Event-ID`는 MVP에서는 필수가 아니며, 재연결 시 현재 job 상태와 최근 결과를 다시 전송한다.

### POST `/documents/{document_id}/analysis/cancel`

정말 취소 가능한 `queued/running` 작업에만 허용한다. 외부 Vector Store 호출 중이면 즉시 중단하지 못할 수 있고, local job을 `cancel_requested`로 표시한 뒤 안전한 경계에서 종료한다.

Response `202 data`: `{document_id, job_id, status: "cancel_requested"}`.

### GET `/documents/{document_id}/chunks/{chunk_id}`

청크가 해당 문서에 속하지 않으면 404로 처리한다.

Response `data`: `DocumentChunk` + `document_title` + `concepts` + `neighbors`.

### GET `/documents/{document_id}/original`

로컬 원문 asset에서 읽기용 구간을 반환한다. 원문 전체를 요청할 수 있지만 프론트는 근거 위치 중심으로 range를 요청한다.

Query:

| 파라미터 | 타입 | 기본 | 설명 |
|---|---|---:|---|
| `start_char` | integer | 0 | 0 이상 |
| `end_char` | integer or null | 문서 끝 | exclusive, 최대 window 제한 적용 |
| `context_chars` | integer | 1,000 | 선택 위치 앞뒤 문맥. 0~10,000 |

Response `data`:

| 필드 | 타입 | 설명 |
|---|---|---|
| `document_id` | integer | 문서 ID |
| `content` | string | 요청 범위의 원문 |
| `start_char` | integer | 실제 반환 시작 offset |
| `end_char` | integer | 실제 반환 끝 offset |
| `total_character_count` | integer | 전체 원문 길이 |
| `highlight_start_char` | integer or null | content 기준 강조 시작 |
| `highlight_end_char` | integer or null | content 기준 강조 끝 |

원문 파일이 없거나 삭제 중이면 `DOCUMENT_SOURCE_UNAVAILABLE`을 반환하고 snapshot source는 계속 표시한다.

## 8. Concepts

### GET `/concepts/{concept_id}`

Query:

| 파라미터 | 기본 | 설명 |
|---|---:|---|
| `include_sources` | true | 출처 청크 포함 |
| `include_related` | true | 관계 개념 포함 |
| `sources_page_size` | 20 | 1~100 |

Response `data`: `ConceptDetail`.

숨김/고립 개념은 direct URL에서 상세를 열 수 있지만 `visibility`를 표시하고, graph 기본 snapshot에서는 제외한다.

## 9. Graph

### GET `/graph`

Query:

| 파라미터 | 타입 | 기본 | 설명 |
|---|---|---:|---|
| `node_types` | enum[] | `document,concept` | `document,chunk,concept` |
| `concept_types` | enum[] | all | ConceptType filter |
| `include_chunks` | boolean | false | 선택 문서/전체 청크 |
| `focus_type` | enum | none | document/concept/chunk |
| `focus_id` | integer | none | focus와 함께 필요 |
| `depth` | integer | 1 | focus graph 1~2 |
| `recent_days` | integer | none | 최근 문서만 |
| `min_strength` | number | 0 | 0~1 |
| `limit_nodes` | integer | 500 | 1~2,000 |
| `limit_edges` | integer | 1,500 | 1~5,000 |

규칙:

- 기본은 document+concept이며 청크는 숨긴다.
- `focus_type/focus_id`가 있으면 해당 node 주변 depth를 우선한다.
- limit을 초과하면 고립 node보다 edge strength가 높은 연결을 우선하고 `truncated=true`로 표시한다.
- 삭제·processing 상태 문서와 그 파생 node는 제외한다.

Response `data`: `GraphSnapshot`.

## 10. Questions

### POST `/questions`

사용자에게 노출되는 유일한 검색/AI 질문 진입점이다. 키워드 입력도 질문으로 취급한다.

Request body:

| 필드 | 타입 | 필수 | 기본 | 설명 |
|---|---|---:|---:|---|
| `question` | string | Y |  | 2~1,000자 |

처리 순서:

1. 유효성·빈 지식공간 확인.
2. 질문 history를 queued로 생성.
3. OpenAI Vector Store에서 전체 원문 기준 관련 결과를 최대 3개 retrieval.
4. provider result content를 local document/chunk와 mapping.
5. 매핑된 근거만 Responses API에 제공.
6. 답변의 citation marker와 source rank를 검증.
7. history/source snapshot 저장 후 completed 반환.

Response:

- 동기 완료: `201 Created`, `data=QuestionResult`.
- 처리 시간이 길어 timeout 전에 전환하면 `202 Accepted`, `data=QuestionResult`이며 status는 `queued/retrieving/generating`이다. 클라이언트는 반환된 `id`로 `GET /questions/{question_id}`를 polling한다. 질문 전용 SSE는 MVP 범위에 포함하지 않는다.

답변 규칙:

- 0개 근거면 `status=no_evidence`, answer는 자료 부족 안내, 일반 상식 생성 금지.
- 1~2개 근거면 실제 개수만 표시.
- 동일 문서의 청크가 여러 개면 source document link는 중복 제거.
- 답변에 없는 source를 source list에 넣지 않는다.

### GET `/questions`

Query: `page`, `page_size`, `status`, `created_from`, `created_to`, `sort=created_at`, `order=desc`.

Response items:

| 필드 | 타입 |
|---|---|
| `id` | integer |
| `question_preview` | string |
| `status` | QuestionStatus |
| `answer_preview` | string or null |
| `evidence_count` | integer |
| `created_at` | datetime |
| `completed_at` | datetime or null |

### GET `/questions/{question_id}`

Response `data`: 전체 `QuestionResult`와 `history_state`.

`history_state`:

| 필드 | 타입 | 설명 |
|---|---|---|
| `has_stale_sources` | boolean | 삭제/재분석 snapshot 존재 |
| `stale_source_count` | integer | 현재 이동 불가 근거 수 |
| `can_rerun` | boolean | 현재 질문을 다시 실행 가능한지 |

### POST `/questions/{question_id}/rerun`

Request body: `{question?: string}`. 생략하면 기존 질문, 입력하면 수정 질문으로 새 history를 만든다. 기존 history는 변경하지 않는다.

Response `202 data`: 새 `QuestionResult`의 `id`, `question`, `status=queued`와 `created_at`. 기존 history는 변경하지 않는다.

### DELETE `/questions/{question_id}`

질문 기록과 source snapshot을 삭제한다. 문서·개념에는 영향을 주지 않는다. 성공은 body 없는 `204 No Content`로 반환한다. `204`는 envelope을 사용하지 않는다.

## 11. Async job / SSE 공통

현재 MVP에서는 분석 job을 DB에 기록하고 질문은 `question_histories.status`를 polling 가능한 resource 상태로 사용한다. 별도 queue 제품은 추가하지 않으며, 분석은 SSE로 실시간 preview를 제공한다.

`AnalysisJob`:

| 필드 | 타입 |
|---|---|
| `id` | integer |
| `document_id` | integer |
| `status` | enum |
| `stage` | enum |
| `progress` | integer |
| `message` | string |
| `retry_count` | integer |
| `error` | Error or null |
| `started_at/completed_at` | datetime or null |

SSE 규칙:

- `Content-Type: text/event-stream`.
- event data는 JSON object.
- heartbeat interval 15초.
- 서버가 이벤트를 보낼 때마다 `id`를 monotonic job event sequence로 부여한다.
- 연결이 끊겨도 DB 상태가 source of truth다.

## 12. OpenAI 연동 계약

세부 provider 사용법은 `docs/external/openai.md`를 따른다. API layer는 provider 객체를 직접 호출하지 않는다.

### 12.1 Vector Store

- 원문 asset 전체를 Vector Store 파일로 등록한다.
- `documents.vector_store_file_id`에 외부 file ID를 보관한다.
- indexing 완료 전에는 `ready`로 승격하지 않는다.
- provider 검색 결과에는 `file_id`, score, content, attributes가 들어온다고 가정하고 local document와 매핑한다.
- 파일 삭제·재등록은 idempotency 기준으로 처리하고 DB status에 반영한다.

### 12.2 Responses API

- 분석: structured output으로 summary/keywords/concepts/relations를 요청한다.
- 답변: 검색된 최대 3개 local evidence를 명시적 context로 전달하고, citation key를 요구한다.
- API key는 backend 환경변수에서만 읽는다.
- model 이름·reasoning effort·verbosity는 settings로 주입하며 문서에 특정 모델 ID를 고정하지 않는다.
- provider timeout·429·5xx는 표준 error로 변환하고, 원문/질문을 잃지 않으며 retryable을 true로 표시한다.

## 13. CORS·보안·캐시

- 개발: Vite origin만 allow. 운영: 동일 origin 또는 명시된 allowlist만 허용.
- API key·Vector Store ID를 frontend 응답에 반환하지 않는다. status에는 configured boolean만 반환한다.
- 원문 GET는 기본 no-store. 질문 답변도 개인정보가 포함될 수 있으므로 cache-control no-store.
- 업로드는 multipart boundary와 content length를 검증한다.
- 모든 path parameter는 정수 검증. 파일명은 서버에서 정규화.
- 현재 인증은 없지만, 외부에 공개 bind하지 않는 것을 운영 조건으로 한다.

## 14. API 수용 테스트

- 모든 2xx가 `data/meta/error` 계약을 지킨다. 단, DELETE 204 예외는 문서화된 대로 처리한다.
- 400/404/409/422/502가 동일 error envelope을 반환한다.
- page/page_size와 filter가 모든 목록 endpoint에서 동일하게 동작한다.
- 문서 업로드는 202와 job을 즉시 반환하고, SSE reconnect 후 최종 상태가 재현된다.
- 질문 결과의 source rank/citation key/local chunk mapping이 일치한다.
- 삭제된 문서가 graph·new question retrieval에 나오지 않고, old question history snapshot은 열린다.
- 질문 기록 rerun은 기존 기록을 수정하지 않는다.
