# 01. Database Model

- 문서 상태: Reviewed / runtime contract
- 기준 문서: `docs/PRD.md`
- 대상: FastAPI + SQLModel + SQLite + Alembic
- 목적: 문서·청크·개념 그래프·질문 기록·분석 작업을 재현 가능하게 저장하고, 로컬 단일 사용자 MVP에서 확장 가능한 데이터 경계를 정의한다.

## 1. 설계 결정

| 항목 | 결정 |
|---|---|
| 사용자/권한 | 계정·workspace·tenant 테이블을 만들지 않는다. 실행 환경 자체를 단일 지식 공간으로 취급한다. |
| 식별자 | 내부·API 모두 양의 정수 `INTEGER`를 사용한다. 파일명·그래프 노드 ID는 별도 문자열을 조합한다. |
| 시간 | DB에는 UTC timezone-aware ISO 8601 의미로 저장한다. SQLite 저장값은 UTC `YYYY-MM-DDTHH:MM:SS.ssssssZ` 문자열로 표준화한다. |
| 원문 | 업로드 원본과 붙여넣은 원문은 로컬 파일 시스템에 저장한다. DB에는 경로 키·해시·메타데이터만 저장한다. |
| 검색 텍스트 | 분석·근거에 사용할 내부 청크 본문은 SQLite에 저장하고 FTS5에 색인한다. |
| AI 검색 | 문서 전체 원문 파일을 OpenAI Vector Store에 등록한다. Vector Store의 파일 ID를 문서에 매핑한다. |
| 그래프 | 문서→청크는 FK, 청크→개념은 association, 개념↔개념은 명시적 relation으로 구성한다. 문서·개념 직접 연결은 조회 시 파생한다. |
| 삭제 | 사용자 화면에서 즉시 숨긴 뒤 로컬 파일·DB·Vector Store 파일을 순서대로 정리한다. 질문 기록은 근거 snapshot을 보존한다. |
| 분석 | 분석 작업을 DB에 기록한다. 프로세스 재시작 시 `queued/running` 작업을 복구 가능한 상태로 남긴다. |
| JSON | 검색 가능한 핵심 관계는 정규화 테이블로 저장한다. UI 편의용 원본 모델·설정 snapshot만 JSON 문자열을 사용한다. |

## 2. 도메인 관계

```text
Document 1 ─── N DocumentChunk N ─── N Concept
Document 1 ─── N AnalysisJob
Concept 1 ─── N ConceptAlias
Concept 1 ─── N ConceptRelation ─── 1 Concept
ConceptRelation N ─── 1 DocumentChunk (evidence)
ChatConversation 1 ─── N QuestionHistory 1 ─── N QuestionSourceSnapshot N ─── 0..1 DocumentChunk
```

### 2.1 Runtime 검증 결과

- 실제 SQLModel/Alembic head는 문서·청크·FTS5·개념·alias·relation·분석 job·질문 history/source snapshot을 사용한다.
- 원문은 `backend/data/storage/`에 저장하고 `documents.storage_key`로 참조한다. DB의 임시 분석 필드는 원문 source of truth가 아니다.
- Vector Store indexing 실패 시 현재 구현은 로컬 원문·FTS·분석 결과를 보존하고 로컬 검색 가능한 `ready`로 남길 수 있다. `ready`는 외부 Vector Store 성공을 절대 전제하지 않으며, 외부 상태는 `vector_store_status`로 확인한다.
- `active_job_id`는 현재 migration에서 논리적 참조이며 DB foreign key가 아니다. job 일관성은 service 계층에서 검증한다.
- 스키마 변경은 SQLModel 수정만으로 끝내지 않고 Alembic revision과 empty/current DB upgrade 테스트를 함께 추가한다.

### 2.2 사용자에게 보이는 객체와 저장 객체

| 사용자 객체 | 저장 객체 | 비고 |
|---|---|---|
| 자료/문서 | `documents` + local asset | 원문, 제목, 상태, 분석 요약 |
| 문서 청크 | `document_chunks` + `chunk_fts` | 24,000자 단위, 500자 overlap |
| 개념 노드 | `concepts` | 13개 타입 중 하나 |
| 개념의 다른 이름 | `concept_aliases` | 한글명·영문명·약어와 출처 |
| 개념 간 연결 | `concept_relations` | 관계명·강도·근거 청크 |
| 분석 진행 | `analysis_jobs` | SSE와 재시도 기준 |
| 대화 | `chat_conversations` | 대화 제목·상태·최근 활동 |
| AI 질문/turn 기록 | `question_histories` | turn별 질문·답변과 당시 근거 snapshot |
| 답변 참고 자료 | `question_sources` | 삭제·재분석 뒤에도 표시 가능 |

## 3. 공통 규칙

### 3.1 공통 컬럼

모든 영속 테이블은 다음 공통 규칙을 따른다.

- `id`: `INTEGER PRIMARY KEY`.
- `created_at`: 생성 시각.
- `updated_at`: 사용자가 수정 가능한 객체에만 둔다.
- 상태값은 자유 텍스트가 아니라 문서에 정의된 enum의 문자열로 저장한다.
- FK 삭제 정책은 기본 `RESTRICT`; 명시된 관계만 `CASCADE` 또는 `SET NULL`을 사용한다.
- API에 반환하는 날짜는 항상 `Z`가 붙은 UTC ISO 8601 문자열이다.
- 내부 오류·외부 API 원문 응답·API 키는 DB에 저장하지 않는다.

### 3.2 상태 enum

#### DocumentStatus

`draft`, `processing`, `ready`, `failed`, `deleting`, `deleted`

- `draft`: 원문은 임시 보관되었지만 그래프·질문에 사용하지 않는다.
- `processing`: 분석 작업이 진행 중이다.
- `ready`: 로컬 원문·청크·FTS·개념·관계가 조회 가능한 상태다. Vector Store 상태는 별도 필드로 판단한다.
- `failed`: 원문은 보존되며 분석 재시도가 가능하다.
- `deleting`: 사용자에게 숨겨지고 정리 작업 중이다.
- `deleted`: 논리 상태 기록이 필요한 경우에만 남기며 기본 조회에서는 제외한다.

#### AnalysisJobStatus

`queued`, `running`, `completed`, `failed`, `cancel_requested`, `canceled`

#### AnalysisStage

`received`, `stored`, `chunking`, `summarizing`, `extracting_concepts`, `linking_concepts`, `finalizing`, `completed`, `failed`, `canceled`

Vector Store 등록은 로컬 분석 job 완료 뒤 별도 `documents.vector_store_status`로 추적하므로 분석 progress stage에 섞지 않는다.

#### ConceptType

`organization`, `organization_unit`, `person`, `country`, `region`, `place`, `technology`, `equipment`, `system`, `project_program`, `policy_law`, `event`, `document`

#### SourceType

`paste`, `upload`

#### QuestionStatus

`queued`, `retrieving`, `generating`, `completed`, `no_evidence`, `failed`

## 4. 테이블 정의

### 4.1 `documents`

문서의 정체성·원문 asset·분석 결과·외부 검색 인덱스 매핑을 보관한다.

| 컬럼 | SQLite 타입 | Null | 기본값/제약 | 설명 |
|---|---|---:|---|---|
| `id` | INTEGER | N | PK | 문서 ID |
| `source_type` | TEXT | N | enum | `paste`, `upload`, `ai_generated` |
| `original_filename` | TEXT | Y | max 255 | 업로드 원본 파일명. 붙여넣기는 null 가능 |
| `media_type` | TEXT | N | `text/plain` 등 | 원문 형식 |
| `storage_key` | TEXT | N | unique | 실제 파일 시스템 경로가 아닌 상대 키 |
| `title` | TEXT | N | max 255 | 자동 추출 후 사용자 수정 가능 |
| `title_source` | TEXT | N | `pending/generated/user` | 사용자 확정 제목의 재분석 덮어쓰기 방지 |
| `summary` | TEXT | N | empty string | 짧은 핵심 요약 |
| `content_hash` | TEXT | N | unique among active | 원문 SHA-256. 중복 감지 |
| `character_count` | INTEGER | N | >= 1 | 정규화된 원문 길이 |
| `status` | TEXT | N | `draft` | DocumentStatus |
| `analysis_version` | INTEGER | N | 0 | 성공한 분석 버전. 최초 완료 1 |
| `active_job_id` | INTEGER | Y | FK | 현재 작업. 완료 시 null |
| `vector_store_file_id` | TEXT | Y | index | OpenAI Vector Store에 등록된 파일 ID |
| `vector_store_status` | TEXT | N | `not_uploaded` | `not_uploaded`, `stale`, `uploading`, `indexed`, `failed`, `deleting`, `deleted` |
| `vector_store_error_code` | TEXT | Y |  | 외부 오류 분류 코드만 저장 |
| `created_at` | TEXT | N | UTC | 생성 시각 |
| `updated_at` | TEXT | N | UTC | 마지막 변경 시각 |
| `deleted_at` | TEXT | Y | UTC | 삭제 완료 시각 |

규칙:

- `status=ready`일 때 `storage_key`, `character_count`, `analysis_version`, 청크 1개 이상과 FTS 반영을 보장한다. Vector Store는 `indexed`가 아니어도 되며 질문은 로컬 FTS로 degraded 동작한다.
- `content_hash`는 `deleted` 문서와 비교하지 않는다. 삭제 후 같은 원문을 재등록할 수 있다.
- 원문 파일은 `documents/{id}/original/{safe-filename}`에 두며 `storage_key`는 이 논리 키만 가진다.
- `active_job_id`는 최대 하나다. 재분석 시 기존 작업을 종료한 뒤 새 작업을 연결한다.

수정 규칙:

- 제목 수정은 `title`, `updated_at`만 변경하며 분석 버전을 증가시키지 않는다.
- 사용자가 제목을 입력·수정하면 `title_source=user`로 고정하고 이후 재분석은 제목을 덮어쓰지 않는다. 제목을 생략한 신규 문서는 `pending`, 첫 분석 제목 적용 후 `generated`다.
- 원문 수정은 새 hash·character count·storage asset을 기록하고 `analysis_version`을 증가시킨다.
- 원문 수정 중에는 `status=processing` 또는 `draft`이며, 새 분석 성공 시 기존 청크·키워드·근거 관계를 새 결과로 교체한다.
- 질문 history의 source snapshot은 원문 수정과 무관하게 당시 내용을 보존한다.

인덱스:

- unique partial index: 활성 상태(`deleted` 제외)의 `content_hash`.
- index: `status`, `created_at DESC`, `updated_at DESC`, `vector_store_file_id`.

### 4.2 `document_chunks`

그래프·FTS·질문 근거의 공통 단위다.

| 컬럼 | SQLite 타입 | Null | 제약 | 설명 |
|---|---|---:|---|---|
| `id` | INTEGER | N | PK | 청크 ID |
| `document_id` | INTEGER | N | FK → documents, CASCADE | 소속 문서 |
| `chunk_index` | INTEGER | N | unique(document_id, chunk_index), >= 0 | 문서 내 순서 |
| `start_char` | INTEGER | N | >= 0 | 원문 정규화 문자열 기준 시작 offset |
| `end_char` | INTEGER | N | > start | 끝 offset, exclusive |
| `content` | TEXT | N | non-empty | 청크 본문 |
| `character_count` | INTEGER | N | > 0 | `end_char - start_char`와 일치 |
| `content_hash` | TEXT | N |  | 청크 SHA-256 |
| `created_at` | TEXT | N | UTC | 생성 시각 |

규칙:

- 24,000자를 넘는 문서는 최대 24,000자, 연속 청크 overlap 500자로 나눈다.
- 문단 경계를 우선하되 목표 범위를 크게 벗어나지 않는다. offset은 최종 정규화 원문 기준으로 계산한다.
- 원문 길이가 24,000자 이하라면 1개 청크다.
- 2개 이상 청크 문서의 그래프는 문서→청크만 직접 연결하고, 개념은 실제 발견된 청크에 연결한다.
- 청크 본문은 검색·근거 표시를 위해 DB에 둔다. 원문 파일이 삭제되기 전까지 offset으로 원문 강조가 가능해야 한다.

인덱스:

- unique: `(document_id, chunk_index)`.
- index: `(document_id, start_char)`, `content_hash`.

### 4.3 `chunk_fts` (SQLite FTS5)

SQLite FTS5 virtual table이다. 별도 일반 테이블의 대체가 아니라 `document_chunks`를 빠르게 찾기 위한 검색 인덱스다.

| 컬럼 | 타입/옵션 | 설명 |
|---|---|---|
| `chunk_id` | UNINDEXED | `document_chunks.id` |
| `document_id` | UNINDEXED | filter/join용 |
| `title` | indexed | 문서 제목 |
| `content` | indexed | 청크 본문 |
| `keywords` | indexed | 정규화 키워드 문자열 |

운영 규칙:

- 청크 insert/update/delete와 FTS insert/update/delete는 같은 서비스 트랜잭션에서 처리한다.
- FTS의 `rowid`를 외부 계약으로 사용하지 않는다. API에는 `chunk_id`만 반환한다.
- 기본 tokenizer는 `unicode61`; 한국어 형태소 분석을 전제하지 않는다. 의미 검색은 Vector Store가 담당한다.
- 사용자에게 노출되는 별도 검색 진입점은 없지만, 질문 결과의 lexical 보정과 제목·키워드 필터에 FTS를 사용한다.

### 4.4 `document_keywords`

문서의 키워드를 정규화해 보관한다. API에서는 문자열 배열로 조합한다.

| 컬럼 | SQLite 타입 | Null | 설명 |
|---|---|---:|---|
| `document_id` | INTEGER | N | FK → documents, CASCADE |
| `keyword` | TEXT | N | 표시용 키워드 |
| `normalized_keyword` | TEXT | N | 검색·중복 비교용 |
| `rank` | INTEGER | N | 문서 내 우선순위 |
| `source` | TEXT | N | `ai`, `fallback`, `user` |
| `created_at` | TEXT | N | UTC |

PK는 `(document_id, normalized_keyword)`로 한다. index는 `(normalized_keyword, document_id)`다.

### 4.5 `concepts`

여러 자료에서 재사용되는 정규화 개념 노드다.

| 컬럼 | SQLite 타입 | Null | 제약 | 설명 |
|---|---|---:|---|---|
| `id` | INTEGER | N | PK | 개념 ID |
| `concept_type` | TEXT | N | ConceptType | 개념 분류 |
| `canonical_name` | TEXT | N | 1~255 | 화면 대표명 |
| `english_name` | TEXT | Y | max 255 | 영문명/원문 표기 |
| `abbreviation` | TEXT | Y | max 100 | 약어 |
| `normalized_name` | TEXT | N | index | 대표명 정규화 값 |
| `description` | TEXT | N | max 500 | 짧은 설명 |
| `merge_confidence` | REAL | N | 0~1 | 기존 개념에 병합된 신뢰도 |
| `visibility` | TEXT | N | `visible` | `visible`, `hidden`, `orphaned` |
| `created_at` | TEXT | N | UTC | 생성 시각 |
| `updated_at` | TEXT | N | UTC | 변경 시각 |

병합 규칙:

1. 한글명·영문명·약어 각각에 대해 공백·대소문자·일반 구두점을 제거한 비교값을 만든다.
2. 같은 `concept_type`에서 alias 비교값이 정확히 일치하면 기존 개념 후보로 둔다.
3. 분류가 다르거나 부분 일치만 있는 경우 자동 병합하지 않는다.
4. 후보가 여러 개면 자동 병합하지 않고 유사 개념으로 표시한다.
5. 사용자가 숨긴 개념은 다음 분석에서 자동으로 다시 표시하지 않는다.

인덱스:

- index: `(concept_type, normalized_name)`.
- index: `visibility`, `updated_at DESC`.

### 4.6 `concept_aliases`

개념의 한글명·영문명·약어·원문 표현과 출처를 보관한다.

| 컬럼 | SQLite 타입 | Null | 설명 |
|---|---|---:|---|
| `id` | INTEGER | N | PK |
| `concept_id` | INTEGER | N | FK → concepts, CASCADE |
| `alias` | TEXT | N | 실제 표기 |
| `normalized_alias` | TEXT | N | 비교용 정규화 값 |
| `alias_type` | TEXT | N | `ko`, `en`, `abbreviation`, `source_mention` |
| `source_chunk_id` | INTEGER | Y | FK → document_chunks, SET NULL |
| `confidence` | REAL | N | 0~1 |
| `created_at` | TEXT | N | UTC |

중복 `(concept_id, normalized_alias, alias_type)`는 허용하지 않는다. 다른 개념에서 같은 alias가 발견될 수 있으므로 전역 unique는 만들지 않고 병합 후보 조회용 index만 만든다.

### 4.7 `chunk_concepts`

청크에서 개념이 발견된 사실과 노출 위치를 저장한다.

| 컬럼 | SQLite 타입 | Null | 설명 |
|---|---|---:|---|
| `chunk_id` | INTEGER | N | FK → document_chunks, CASCADE |
| `concept_id` | INTEGER | N | FK → concepts, CASCADE |
| `mention` | TEXT | N | 원문에 나타난 표현 |
| `mention_start` | INTEGER | Y | 청크 내 시작 offset |
| `mention_end` | INTEGER | Y | 청크 내 끝 offset |
| `extraction_confidence` | REAL | N | 0~1 |
| `description_snapshot` | TEXT | N | 추출 당시 짧은 설명 |
| `created_at` | TEXT | N | UTC |

PK는 `(chunk_id, concept_id, mention)`으로 한다. 같은 청크에서 같은 개념이 여러 표현으로 나오면 mention별 row를 허용한다.

### 4.8 `concept_relations`

개념과 개념 사이의 관계를 저장한다. 문서·청크 연결은 각각의 FK/association에서 파생한다.

| 컬럼 | SQLite 타입 | Null | 제약/설명 |
|---|---|---:|---|
| `id` | INTEGER | N | PK |
| `source_concept_id` | INTEGER | N | FK → concepts |
| `target_concept_id` | INTEGER | N | FK → concepts, source와 다름 |
| `relation_type` | TEXT | N | `소속`, `사용`, `위치`, `개발`, `참여`, `발생`, `관련`, `언급`, `유사` 또는 확장 registry 값 |
| `is_directed` | INTEGER | N | 0/1 |
| `strength` | REAL | N | 0~1 |
| `extraction_confidence` | REAL | N | 0~1 |
| `explanation` | TEXT | N | 짧은 관계 설명 |
| `evidence_chunk_id` | INTEGER | Y | FK → document_chunks, CASCADE. 근거 청크가 사라지면 해당 근거 관계도 제거 |
| `visibility` | TEXT | N | `visible`, `hidden` |
| `created_at` | TEXT | N | UTC |
| `updated_at` | TEXT | N | UTC |

규칙:

- 근거 청크에 명시된 관계만 `strength >= 0.5`의 강한 관계로 저장한다.
- 동일 문서에 함께 있다는 사실만으로 concept relation을 만들지 않는다.
- 의미 유사도만으로 연결한 관계의 type은 `유사`이고, UI에서 점선/낮은 강도로 표시한다.
- 같은 방향·관계·근거 청크의 중복 row를 만들지 않는다.

### 4.9 `analysis_jobs`

문서 분석의 durable 상태와 SSE 진행 정보를 저장한다.

| 컬럼 | SQLite 타입 | Null | 설명 |
|---|---|---:|---|
| `id` | INTEGER | N | PK |
| `document_id` | INTEGER | N | FK → documents, CASCADE |
| `status` | TEXT | N | AnalysisJobStatus |
| `stage` | TEXT | N | AnalysisStage |
| `progress` | INTEGER | N | 0~100. 의미상 추정치이며 완료 시 100 |
| `message` | TEXT | N | 사용자에게 보여줄 짧은 상태 |
| `analysis_version` | INTEGER | N | 대상 결과 버전 |
| `retry_count` | INTEGER | N | 재시도 횟수 |
| `error_code` | TEXT | Y | 표준 application error code |
| `error_message` | TEXT | Y | 사용자 안전 메시지. secret 제외 |
| `cancel_requested_at` | TEXT | Y | 취소 요청 시각 |
| `started_at` | TEXT | Y | 시작 시각 |
| `completed_at` | TEXT | Y | 종료 시각 |
| `created_at` | TEXT | N | 생성 시각 |
| `updated_at` | TEXT | N | 변경 시각 |

인덱스: `(document_id, created_at DESC)`, `(status, created_at)`.

### 4.10 `chat_conversations`

하나의 멀티턴 대화를 저장한다. 계정·workspace FK는 두지 않는다.

| 컬럼 | SQLite 타입 | Null | 설명 |
|---|---|---:|---|
| `id` | INTEGER | N | PK |
| `title` | TEXT | N | 자동 생성 또는 사용자 수정 제목 |
| `title_source` | TEXT | N | `auto` 또는 `user` |
| `status` | TEXT | N | `active`, `archived`, `deleted` |
| `turn_count` | INTEGER | N | 저장된 turn 수 |
| `last_turn_at` | TEXT | Y | 마지막 turn 시각 |
| `created_at` | TEXT | N | UTC |
| `updated_at` | TEXT | N | UTC |
| `deleted_at` | TEXT | Y | 삭제 시각 |

index: `(status, last_turn_at DESC)`.

대화 삭제는 해당 turn과 source snapshot을 함께 삭제하며 문서·개념 데이터에는 영향을 주지 않는다.

### 4.11 `question_histories`

대화 안의 질문 1개와 그에 대한 답변을 하나의 turn으로 저장한다. 기존 단일 질문 기록도 migration에서 1개 대화의 1번 turn으로 backfill한다.

| 컬럼 | SQLite 타입 | Null | 설명 |
|---|---|---:|---|
| `id` | INTEGER | N | PK |
| `conversation_id` | INTEGER | Y | FK → chat_conversations, legacy 호환을 위해 초기 nullable |
| `turn_index` | INTEGER | Y | 대화 안 순서, 1부터 시작 |
| `question` | TEXT | N | 2~1,000자 |
| `status` | TEXT | N | QuestionStatus |
| `answer_markdown` | TEXT | Y | 완료된 답변 |
| `answer_language` | TEXT | Y | 질문 언어 판정 결과 |
| `model_name` | TEXT | Y | 생성에 사용한 모델 식별자 |
| `retrieval_provider` | TEXT | N | `vector_store`, `lexical_fallback`, `none` |
| `retrieval_candidate_count` | INTEGER | N | provider가 반환한 후보 수 |
| `retrieval_mapping_failures` | INTEGER | N | local chunk로 연결하지 못한 후보 수 |
| `retrieval_count` | INTEGER | N | 실제 근거 수 |
| `citation_count` | INTEGER | N | 답변에 사용된 citation 수 |
| `retrieval_query` | TEXT | Y | 실제 검색에 사용한 standalone query |
| `context_turn_count` | INTEGER | N | 답변 생성에 사용한 이전 완료 turn 수 |
| `context_truncated` | INTEGER | N | context 예산으로 절단되었는지 |
| `error_code` | TEXT | Y | 실패 분류 |
| `error_message` | TEXT | Y | 사용자 안전 메시지 |
| `created_at` | TEXT | N | 질문 실행 시각 |
| `completed_at` | TEXT | Y | 답변 완료 시각 |

질문 완료 전에 `status=queued/retrieving/generating`을 저장하고, UI가 기록을 새로고침해도 진행 상태를 표시할 수 있게 한다. index는 `(conversation_id, turn_index)`, `(status, created_at)`를 사용하고 `(conversation_id, turn_index)`는 unique로 둔다.

### 4.12 `question_sources`

질문 당시의 근거를 snapshot으로 보존한다. 문서 삭제·재분석이 질문 기록을 망가뜨리지 않게 하는 핵심 테이블이다.

| 컬럼 | SQLite 타입 | Null | 설명 |
|---|---|---:|---|
| `id` | INTEGER | N | PK |
| `question_history_id` | INTEGER | N | FK → question_histories, CASCADE |
| `rank` | INTEGER | N | 1~3 |
| `chunk_id` | INTEGER | Y | 현재 chunk. 삭제 시 null |
| `document_id` | INTEGER | Y | 현재 document. 삭제 시 null |
| `document_title_snapshot` | TEXT | N | 당시 제목 |
| `document_filename_snapshot` | TEXT | Y | 당시 파일명 |
| `chunk_content_snapshot` | TEXT | N | 당시 청크 미리보기/근거 본문 |
| `start_char_snapshot` | INTEGER | Y | 당시 위치 |
| `end_char_snapshot` | INTEGER | Y | 당시 위치 |
| `score` | REAL | N | 검색 당시 점수 |
| `citation_key` | TEXT | N | `S1`, `S2`, `S3` |
| `mapping_confidence` | REAL | N | Vector Store 결과와 local chunk 매핑 신뢰도 |
| `current_state` | TEXT | N | `current`, `document_deleted`, `document_reanalyzed`, `mapping_unavailable` |
| `created_at` | TEXT | N | UTC |

unique `(question_history_id, rank)` 및 `(question_history_id, citation_key)`.

## 5. 설정 및 파일 시스템

### 5.1 `app_settings` 선택 테이블

비밀값은 저장하지 않고, 단일 환경의 비밀이 아닌 재사용 가능한 상태만 저장한다.

| key | value 예 | 용도 |
|---|---|---|
| `vector_store_id` | `vs_...` | 단일 Vector Store ID |
| `schema_version` | `2026...` | 데이터 확인 |
| `last_startup_at` | UTC | 운영 상태 |

OpenAI API key, model override, 파일 시스템 root는 `.env`/환경변수로만 관리한다.

### 5.2 파일 저장 규칙

```text
backend/data/
  app.db
  storage/
    documents/{document_id}/original/{safe_filename}
    documents/{document_id}/temp/{upload_id}
  logs/
```

- 사용자가 제공한 파일명은 표시용으로만 사용한다. 실제 파일명은 서버 생성 safe key를 사용한다.
- 경로 traversal(`..`, 절대 경로, null byte)을 거부한다.
- 원문 asset은 DB 트랜잭션 전에 temp에 쓴 뒤 hash·내용 검증 후 최종 경로로 이동한다.
- 삭제 작업은 `deleting` 상태를 먼저 commit하고, 파일 삭제 실패 시 retry 가능한 정리 작업으로 남긴다.
- 백업 시 `app.db`와 `storage/`의 상대 경로 관계를 보존한다.

## 6. 무결성·트랜잭션

### 6.1 등록 트랜잭션

1. temp file 저장 및 원문 정규화/hash 계산.
2. `documents(draft)` 생성.
3. `document_chunks`, `chunk_fts` 생성.
4. 분석 결과의 concepts/aliases/chunk_concepts/relations 저장.
5. `documents.status=ready`, `analysis_jobs.completed`를 같은 DB transaction에서 commit.

Vector Store 등록은 외부 side effect이므로 DB transaction 안에서 network call을 수행하지 않는다. 로컬 결과를 `ready`로 commit한 뒤 외부 등록을 시도하며, 실패하면 문서는 `ready`, `vector_store_status=failed`로 남겨 FTS 질문과 재색인을 허용한다.

### 6.2 재분석

- 원문 hash가 같아도 재분석 요청이면 새 `analysis_version` 작업을 만든다.
- 기존 결과를 먼저 삭제하지 않는다. 새 결과가 완성된 뒤 문서의 active 결과를 교체한다.
- 교체 시 기존 concept relation과 chunk association은 새 결과 기준으로 교체하되, question snapshot은 수정하지 않는다.
- MVP에서 이전 분석 버전 본문까지 복원할 필요는 없으므로 active 결과 1개만 유지한다. 버전 비교는 P1 확장 영역이다.

### 6.3 삭제

1. `documents.status=deleting`을 commit하고 모든 일반 조회에서 제외한다.
2. 새 질문·그래프 조회가 해당 문서를 선택하지 않도록 한다.
3. Vector Store file 삭제를 요청하고 결과를 기록한다.
4. 로컬 원문 asset을 삭제한다.
5. document cascade로 chunks, FTS, association, relation evidence를 정리한다.
6. 사용되지 않는 concept는 `orphaned`로 남겼다가 그래프에서 숨긴다. 질문 snapshot은 유지한다.

## 7. 조회 모델

DB 모델과 API response 모델은 분리한다. 다음 read model을 repository/service에서 조합한다.

| Read model | 포함 정보 |
|---|---|
| `DocumentSummary` | id, title, filename, summary, keywords, status, counts, created_at |
| `DocumentDetail` | summary + original metadata + chunks + concepts + latest job |
| `ChunkEvidence` | chunk id, document id, index, preview/content, offsets, score, citation key |
| `ConceptDetail` | concept fields + aliases + source chunks + related concepts |
| `GraphSnapshot` | nodes, edges, truncation metadata, applied filters |
| `QuestionResult` | question, answer, source evidence, related concepts, retrieval metadata, conversation/turn metadata |
| `ConversationDetail` | conversation summary + ordered question turns |
| `QuestionHistorySummary` | id, conversation id, turn index, question preview, status, answer preview, evidence count, created_at |

## 8. Alembic migration 정책

- 모든 schema 변경은 `backend/alembic/versions/`의 단일 revision으로 만든다.
- 모델 변경 후 migration 생성 → 빈 DB upgrade → 기존 DB upgrade → downgrade 가능성 검토 순서로 검증한다.
- FTS5 virtual table·trigger는 일반 SQLModel metadata만으로 안전하게 생성하지 말고 migration의 explicit SQL로 관리한다.
- 데이터 변환이 필요한 migration은 schema migration과 분리한다.
- 현재 head는 `20260730_0005`다. 과거 `documents.content`, `keywords_json`, `embedding_json`에서 목표 모델로 이동할 때는 다음 순서를 따른다.
  1. 신규 컬럼/테이블 생성.
  2. 기존 원문을 `storage/`로 이동하고 hash/metadata 입력.
  3. 기존 내용으로 chunks/FTS 생성.
  4. 기존 JSON keyword를 `document_keywords` 또는 API read model로 변환.
  5. 애플리케이션 전환 확인 후 legacy 컬럼 제거 migration.

## 9. 데이터 검증 체크리스트

- 문서 1개 입력 → 1개 chunk → concept association.
- 24,000자 정확히 → 1개 chunk; 24,001자 → 2개 chunk, 두 번째 start가 첫 번째 end-500.
- 개념 한글명/영문명/약어 exact normalized match → 기존 개념 재사용.
- 부분 일치/분류 불일치 → 자동 병합 없음.
- 질문 결과 3개 → `question_sources.rank=1..3`, citation `S1..S3`.
- 기존 질문 기록 migration → 기존 row마다 conversation 1개와 `turn_index=1` 생성.
- 같은 대화 후속 질문 → 완료 turn만 context로 사용하고 turn index를 증가시킨다.
- 문서 삭제 후 질문 기록 → snapshot 렌더링, 현재 문서 link는 비활성/상태 표시.
- FTS row 삭제 후 질문 결과 → deleted 문서가 다시 선택되지 않음.
- 분석 중 프로세스 재시작 → running job이 recoverable retry 상태로 전환.
