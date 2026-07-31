# OpenAI API 개발자 레퍼런스

> 기준일: 2026-07-30
> 범위: JSH Second Brain의 문서 분석, OpenAI Vector Store 의미 검색, 근거 기반 답변
> 우선순위: 이 문서의 제품 계약은 `docs/PRD.md`, 저장 계약은 `docs/01_database_model.md`, HTTP 계약은 `docs/02_api_spec.md`를 따른다.

## 1. 확정 결정

| 항목 | 결정 | 이유 |
|---|---|---|
| SDK | OpenAI Python SDK | Responses·Vector Store poll helper·Pydantic Structured Outputs 사용 |
| 생성 API | Responses API | 문서 분석과 근거 기반 답변의 단일 생성 경계 |
| 기본 모델 | `gpt-5.6-terra` | 경량·저지연 역할의 최신 모델. 환경변수로 교체 가능 |
| 의미 검색 | OpenAI Vector Store Search | 전체 원문을 OpenAI 관리형 인덱스에 적재 |
| 로컬 검색 | SQLite FTS5 | Vector Store 미구성·장애·매핑 실패 시 fallback |
| 구조화 분석 | Responses Structured Outputs + Pydantic | 제목·요약·개념·관계 출력 검증 |
| 답변 근거 | 애플리케이션이 선택한 로컬 청크 최대 3개 | 자체 문서 링크와 정확한 원문 위치 보장 |
| 비밀키 | Backend 환경변수 전용 | 브라우저·DB·응답·로그 노출 금지 |

`gpt-5-mini`는 2026-06-11 deprecated 되었고 2026-12-11 종료 예정이므로 신규 기본값으로 사용하지 않는다. OpenAI는 해당 역할의 대체 모델로 `gpt-5.6-terra`를 안내한다. 모델명은 `OPENAI_CHAT_MODEL`로 주입하며 코드에 고정하지 않는다. 대규모 모델 변경 전에는 분석 schema 준수율, 한국어 개념 정규화, citation 정확도, 지연·비용을 회귀 평가한다. [GPT-5 mini 모델](https://developers.openai.com/api/docs/models/gpt-5-mini), [Deprecated API](https://developers.openai.com/api/docs/deprecations), [GPT-5.6 terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra)

## 2. 시스템 책임 경계

```text
브라우저
  → FastAPI
      ├─ Local FS: 원문 source of truth
      ├─ SQLite: 문서·청크·개념·관계·질문·출처 snapshot
      ├─ FTS5: 로컬 lexical fallback
      ├─ OpenAI Vector Store: 원문 semantic index
      └─ Responses API: 구조화 분석·근거 기반 답변
```

- Local FS와 SQLite가 제품 데이터의 source of truth다.
- Vector Store는 검색 인덱스이며 문서 상태·그래프·질문 이력을 대체하지 않는다.
- Responses 출력은 후보 데이터다. Pydantic 검증, enum 검증, 로컬 offset 검증, 개념 중복 병합, citation 검증을 통과한 값만 저장·표시한다.
- OpenAI file ID와 Vector Store ID는 외부 resource mapping이다. 사용자 링크는 항상 로컬 document/chunk ID로 만든다.
- 그래프는 로컬 document/chunk/concept/relation 데이터에서 생성한다. Vector Store가 graph edge를 제공한다고 가정하지 않는다.

## 3. 환경변수와 client 정책

| 환경변수 | 기본값 | 설명 |
|---|---|---|
| `OPENAI_API_KEY` | 없음 | 없으면 AI 미연결 로컬 모드 |
| `OPENAI_CHAT_MODEL` | `gpt-5.6-terra` | 분석·답변 Responses 모델 |
| `OPENAI_VECTOR_STORE_ID` | 없음 | 기존 store 재사용. 없으면 최초 적재 시 생성 가능 |
| `OPENAI_TIMEOUT_SECONDS` | `60` | 일반 OpenAI 요청 timeout |
| `QUESTION_TIMEOUT_SECONDS` | `90` | retrieval+answer 전체 제한 |

Client 규칙:

- 프로세스에서 client를 재사용하고 요청마다 새로 생성하지 않는다.
- SDK `timeout`과 `max_retries`를 명시한다. 현재 구현은 개별 요청 60초, transport retry 2회다.
- 429·5xx·연결 timeout만 제한적으로 재시도한다. schema/validation 4xx는 자동 반복하지 않는다.
- SDK가 제공하는 request ID와 애플리케이션 request/job/document ID를 구조화 로그에 연결하되 API key·원문·질문 전문은 기록하지 않는다.
- API key는 Backend에만 둔다. `VITE_*`, frontend bundle, API 응답, SQLite에 넣지 않는다.
- 개발 `.env`는 Git에서 제외하고 `.env.example`만 커밋한다.

[API key 안전 수칙](https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safety), [Production best practices](https://developers.openai.com/api/docs/guides/production-best-practices), [Rate limits](https://developers.openai.com/api/docs/guides/rate-limits)

## 4. 문서 적재 계약

### 4.1 입력

- 지원: pasted plain text, `.txt`, `.md`, `.pdf`.
- 파일 MIME와 확장자를 함께 검증한다.
- PDF는 텍스트 추출 결과가 비었으면 사용자에게 실패를 반환한다. OCR은 현재 범위가 아니다.
- 파일명은 표시 메타데이터일 뿐 storage path로 직접 사용하지 않는다.
- 원문 hash를 계산해 중복 여부 판단과 재분석 안전성에 사용한다.

### 4.2 순서

1. 입력 크기·형식 검증.
2. 원문을 Local FS에 안전한 storage key로 저장하고 `document=draft` 생성.
3. 원문을 24,000자, overlap 500자로 로컬 청킹. 각 청크에 원문 기준 `start_char/end_char` 저장.
4. Responses로 문서 제목·요약·키워드 구조화 추출. `title_source=user`인 제목은 덮어쓰지 않는다.
5. 청크별 개념과 관계를 구조화 추출하고 로컬 정규화·중복 병합.
6. chunks·FTS·keywords·concepts·relations를 transaction으로 교체.
7. document를 `ready`, analysis job을 `completed`로 전환.
8. 전체 원문 파일을 Vector Store에 upload하고 SDK poll helper로 indexing 완료 대기.
9. 성공 시 `vector_store_status=indexed`; 실패 시 `failed`와 안정적인 오류 code 기록. 로컬 `ready`는 유지.

로컬 검색·그래프 준비와 외부 semantic index 준비를 분리한다. Vector Store가 느리거나 실패했다고 분석 완료 화면을 무한 대기시키지 않는다. 재분석 시 기존 로컬 결과는 새 결과가 final transaction을 통과할 때까지 유지한다.

### 4.3 Vector Store 파일

- 전체 원문을 한 파일로 전달한다. 로컬 24,000/500 청킹 규칙을 OpenAI 내부 chunking 규칙과 동일하다고 가정하지 않는다.
- 파일 검색 결과를 로컬 청크에 다시 매핑해야 하므로 document row에 provider file ID를 저장한다.
- upload/index는 비동기일 수 있다. 수동 sleep loop보다 SDK의 `upload_and_poll`/`create_and_poll` 계열 helper를 사용한다.
- 새 파일 indexing 성공 전에는 기존 indexed file mapping을 제거하지 않는다.
- 교체 성공 후 기존 provider file을 삭제한다. 삭제 실패는 cleanup 오류로 기록하고 로컬 최신 mapping은 유지한다.
- 문서 삭제는 UI에서 먼저 숨긴 뒤 provider file과 local asset을 정리한다. provider 장애가 로컬 삭제 완료를 영구 차단하지 않도록 상태를 기록한다.
- 임시 테스트 store에는 만료 정책을 고려할 수 있으나 개인 지식 production store에는 의도치 않은 expiry를 설정하지 않는다.

[Retrieval과 Vector Stores](https://developers.openai.com/api/docs/guides/retrieval), [Files API](https://developers.openai.com/api/reference/resources/files)

## 5. Structured Outputs 분석 계약

Responses의 Pydantic parse 경로를 사용한다. JSON 문자열을 임의 파싱하거나 필수 필드 누락을 보정해 성공 처리하지 않는다. [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [Responses API](https://developers.openai.com/api/reference/resources/responses)

### 5.1 문서 분석

| 필드 | 계약 |
|---|---|
| `title` | 사용자가 입력한 제목이 없을 때 사용할 명확한 제목, 최대 255자 |
| `summary` | 원문에 근거한 압축 요약, 최대 1,000자 |
| `keywords` | 검색 보조 핵심어 3~20개, 중복·일반어 제거 |

### 5.2 개념

각 개념은 최소 `concept_type`, `canonical_name`, `description`, `mention`, `mention_start`, `mention_end`, `confidence`를 가진다. 가능한 경우 `english_name`, `abbreviation`을 생성한다.

허용 type:

`organization`, `organization_unit`, `person`, `country`, `region`, `place`, `technology`, `equipment`, `system`, `project_program`, `policy_law`, `event`, `document`.

규칙:

- 청크당 제품 차원의 고정 node 상한은 두지 않는다. 대신 설명과 관계 표현을 짧게 요구해 output 폭증을 줄인다.
- mention offset은 청크 기준 half-open range `[start, end)`다. 범위를 벗어나거나 실제 mention과 일치하지 않으면 보정 또는 제외한다.
- canonical/English/약어를 모두 alias 후보로 만들되 빈 값은 저장하지 않는다.
- 같은 type에서 한글명 또는 영문 정규화명이 일치하면 기존 concept 재사용을 우선한다.
- 이름 대소문자·Unicode·공백·구두점 정규화는 애플리케이션이 최종 결정한다.
- 재사용된 orphan concept는 다시 visible로 전환한다.

### 5.3 관계

관계는 `source_mention`, `target_mention`, `relation_type`, `explanation`, `confidence`를 가진다.

- 양 끝점이 같은 청크에서 검증된 concept로 매핑되는 경우에만 저장한다.
- 방향이 있는 관계는 source/target을 보존한다.
- 동일 청크·동일 양 끝점·동일 relation type은 중복 저장하지 않는다.
- 관계 evidence는 해당 chunk와 mention 범위를 가리킨다.
- 모델이 원문에 없는 관계를 보완 추론하지 않도록 명시한다.

### 5.4 실패 정책

- API key가 있는데 Responses 호출·Pydantic 검증이 실패하면 단순 keyword fallback으로 정상 완료하지 않는다.
- 원문은 보존하고 job/document를 `failed`로 표시하며 재시도 가능 오류를 제공한다.
- API key가 없는 로컬 모드에서만 제한된 결정적 fallback 분석을 허용한다. 이 결과가 OpenAI 분석인 것처럼 표시하지 않는다.

## 6. 의미 검색과 로컬 매핑

### 6.1 검색

- 사용자 질문 전체를 query로 전달한다.
- OpenAI query rewriting은 검색 품질 평가 후 활성화할 수 있다.
- Vector Search 결과 수는 제품 요구에 맞춰 최대 3개 근거를 만들 수 있을 만큼만 요청한다. API 기본값은 10, 설정 가능한 최대값은 50이다.
- file attribute filter는 collection/source/date 기능이 추가될 때 사용한다.
- score threshold를 낮춰 무조건 3개를 채우지 않는다. 근거가 없으면 `no_evidence`다.

### 6.2 provider result → local chunk

1. provider `file_id`로 `vector_store_status=indexed`인 현재 document를 찾는다.
2. provider content를 공백·개행 기준으로 정규화한다.
3. local chunk exact substring을 우선한다.
4. 없으면 normalized overlap으로 가장 유사한 chunk를 찾는다.
5. confidence가 기준 미만이면 mapping failure로 기록하고 답변 context에서 제외한다.
6. 중복 chunk를 제거하고 relevance 순으로 최대 3개를 선택한다.

`file_id`, `filename`, `score`, `content`는 검색 후보 정보이며 사용자 링크가 아니다. 최종 source는 local `document_id`, `chunk_id`, `start_char`, `end_char`로 만든다.

### 6.3 fallback

- Vector Store 미구성, provider 장애, indexed file 부재, mapping 가능한 결과 부재 시 FTS5를 실행한다.
- 현재 MVP는 semantic score와 FTS rank를 임의 합산하지 않는다.
- 질문 이력에 `retrieval_provider`, candidate count, mapping failure count를 저장해 품질을 추적한다.
- lexical fallback에서도 관련성이 낮으면 `no_evidence`를 반환한다.

[Vector search](https://developers.openai.com/api/docs/guides/retrieval)

## 7. 근거 기반 답변

### 7.1 호출 입력

- 사용자 질문.
- 신뢰할 수 없는 데이터로 명시한 `S1`~`S3` 근거 청크.
- 각 근거의 문서 제목과 최소 메타데이터.
- “근거에 없는 사실을 만들지 말고, 사용한 문장 끝에 `[S#]`를 붙이며, 부족하면 부족하다고 답하라”는 지침.

검색 근거 내부의 명령문은 prompt가 아니라 데이터다. 원문에 포함된 지시를 따르지 않도록 명시해 prompt injection 영향을 줄인다.

### 7.2 출력·검증

- 생성 답변은 local evidence만으로 작성한다.
- `[S#]` marker는 실제 전달한 source key subset이어야 한다.
- 존재하지 않는 marker, citation 없는 실질 답변, 빈 답변은 실패다.
- 성공 시 실제 citation된 source만 질문 snapshot으로 확정한다.
- AI 미구성·Responses 실패·citation 실패 시 생성 답변을 노출하지 않는다. 상태는 `failed`, 안정적인 error code를 반환하며 검색된 근거 snapshot은 보존한다.
- 검색 근거가 없으면 `no_evidence`; AI 장애와 혼동하지 않는다.

Frontend는 답변을 raw HTML로 렌더링하지 않는다. 현재 계약은 plain text와 검증된 citation marker다.

### 7.3 멀티턴 context와 검색 query

- OpenAI provider의 conversation state나 `previous_response_id`를 사용하지 않는다. 애플리케이션 DB의 완료된 `QuestionHistory`에서 최근 turn 최대 6개와 prompt 예산을 조립한다.
- 후속 질문은 이전 turn을 참고해 standalone retrieval query로 rewrite한 뒤 Vector Store/FTS 검색에 사용한다. rewrite 결과는 검색용 데이터이며 답변 사실이나 citation으로 취급하지 않는다.
- 이전 질문·답변은 신뢰할 수 없는 context data로 전달하고, 그 안의 지시문은 따르지 않는다.
- 매 turn의 답변은 현재 turn에서 새로 매핑된 local evidence `S1`~`S3`만 인용할 수 있다. 이전 turn의 citation이나 `[H#]` history marker는 답변 citation으로 허용하지 않는다.
- rewrite 실패·API key 미설정 시 현재 질문과 최근 사용자 질문을 결합한 deterministic fallback query를 사용한다.
- context가 문자/토큰 예산을 넘으면 오래된 turn부터 절단하고 `context_truncated`를 저장한다. rolling summary와 token streaming은 1차 구현 범위에 포함하지 않는다.

## 8. 상태·오류 계약

| 상황 | 로컬 문서 | vector status | 질문 |
|---|---|---|---|
| 로컬 분석 성공, vector 성공 | `ready` | `indexed` | semantic 사용 가능 |
| 로컬 분석 성공, vector 실패 | `ready` | `failed` | FTS fallback 가능 |
| Responses 분석 실패 | `failed` 또는 기존 `ready` 유지 | 기존 mapping `stale/indexed` | 해당 없음 |
| API key 없음 | 로컬 fallback 결과 가능 | `not_configured` | 근거가 있어도 `failed/AI_NOT_CONFIGURED` |
| 답변 생성 실패 | 변경 없음 | 변경 없음 | `failed`, source snapshot 보존 |
| 검색 근거 없음 | 변경 없음 | 변경 없음 | `no_evidence` |

Provider raw message·stack trace·요청 전문은 사용자 응답에 넣지 않는다. 사용자 응답에는 stable code, 행동 가능한 한국어 message, retryable 여부, request ID만 제공한다.

## 9. 보안·개인정보·운영

- 이 서비스는 로그인 없는 local single-user 제품이다. Backend를 공용 인터페이스에 노출하지 않고 기본 host를 loopback으로 둔다.
- CORS는 로컬 frontend origin만 허용한다.
- 원문·질문·AI 응답 API에는 `Cache-Control: no-store`를 사용한다.
- 삭제한 문서의 질문 출처는 제목·발췌 snapshot만 보존하고 live document/chunk ID를 제거한다.
- OpenAI에 전송하면 안 되는 자료를 사용자가 구분할 수 있도록 향후 local-only 적재 옵션을 P3에서 검토한다.
- usage·latency·error rate·vector mapping failure·citation failure를 집계하되 원문은 로그에 넣지 않는다.
- 가격과 rate limit은 계정 tier와 모델에 따라 바뀔 수 있으므로 배포 전 공식 pricing·limits와 응답 header를 확인한다. 하드코딩된 비용 가정을 제품 로직에 넣지 않는다.

[Pricing](https://openai.com/api/pricing/), [Latency optimization](https://developers.openai.com/api/docs/guides/latency-optimization), [Safety best practices](https://developers.openai.com/api/docs/guides/safety-best-practices)

## 10. 구현·검증 체크리스트

### Backend

- [x] OpenAI client를 integration 경계에 격리하고 timeout/retry 설정.
- [x] API key·model·Vector Store ID 환경변수화.
- [x] Responses Pydantic Structured Outputs로 문서·개념·관계 추출.
- [x] 로컬 24,000/500 청크, FTS, 원문 offset 저장.
- [x] 로컬 ready 이후 전체 원문 Vector Store best-effort 동기화.
- [x] Vector result를 local chunk 최대 3개로 매핑하고 FTS fallback.
- [x] 답변 citation 검증과 실패 시 source snapshot 보존.
- [x] 문서 갱신 시 old provider mapping 교체, 삭제 시 provider cleanup 시도.
- [x] provider raw 오류와 validation 입력 비노출.
- [ ] OpenAI integration sandbox/recorded contract test 추가.
- [ ] 모델 변경용 한국어 분석·retrieval·citation 평가 corpus 구축.

### Frontend

- [x] local/AI/vector 연결 상태 구분.
- [x] 분석 실패와 vector degraded를 분리.
- [x] 질문 `failed`, `no_evidence`, `completed`를 별도 표시.
- [x] source click을 local 원문 range로 연결.
- [x] API key를 frontend 환경변수나 bundle에 포함하지 않음.

### 수동 검증

1. API key 없음: 자료는 로컬 분석·그래프·FTS에 적재되고 질문은 가짜 답변 없이 AI 미연결 오류.
2. 정상 key: 문서 분석 완료 후 vector status가 indexed로 전환.
3. provider 장애: 원문·기존 분석 결과 보존, 재시도 가능 상태.
4. 한국어/영문/약어가 같은 개념: 신규 중복보다 alias 재사용.
5. 질문: source 1~3개, 답변 marker와 source rank 일치, source click 원문 위치 이동.
6. 문서 수정: 새 local 결과 성공 전 기존 결과 유지, 성공 후 provider file 교체.
7. 문서 삭제: graph/list 즉시 제외, provider cleanup 시도, 과거 질문 snapshot 유지.

## 11. 공식 문서

- [Models](https://developers.openai.com/api/docs/models)
- [GPT-5.6 terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra)
- [Responses API reference](https://developers.openai.com/api/reference/resources/responses)
- [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [Retrieval / Vector Stores](https://developers.openai.com/api/docs/guides/retrieval)
- [Files API](https://developers.openai.com/api/reference/resources/files)
- [Rate limits](https://developers.openai.com/api/docs/guides/rate-limits)
- [Production best practices](https://developers.openai.com/api/docs/guides/production-best-practices)
- [Deprecations](https://developers.openai.com/api/docs/deprecations)

## 12. 탐색형 Agent 연동 추가 계약

- Responses API의 `tools`에 custom function tool과 hosted `web_search`를 함께 등록한다.
- custom tool은 strict JSON Schema, `additionalProperties=false`, `parallel_tool_calls=false`를 사용한다.
- tool call 결과는 `function_call_output`으로 다음 Responses 호출에 다시 전달한다.
- hosted web search는 신규 연동 기준 `web_search`를 사용하고, 필요 시 `include: ["web_search_call.action.sources"]`로 source metadata를 수집한다.
- web 결과의 `url_citation`을 검증해 `W1..` citation과 URL snapshot으로 저장한다. local source `S1..S3`와 namespace를 섞지 않는다.
- Agent는 provider conversation state에 의존하지 않고 `store=False`와 애플리케이션이 관리하는 최근 3개 완료 turn 및 run trajectory를 사용한다.
- 현재 설정 모델의 hosted web search 지원 여부는 live contract test로 확인한다. 미지원이면 `OPENAI_AGENT_MODEL`을 별도로 설정한다.
