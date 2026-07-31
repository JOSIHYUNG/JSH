# 탐색형 Agent 전환 구현계획

작성 기준: 2026-07-31 · 대상: 현재 코드베이스의 다음 구현 단계

## 1. 목적과 적용 범위

기존 Second Brain의 질문 기능을 고정된 검색→답변 흐름에서, 질문과 최근 대화를 해석해 필요한 도구를 선택하고 도구 결과를 반영해 최종 답변까지 반복하는 탐색형 Agent로 전환한다.

기준 문서는 다음과 같다.

- 제품: docs/PRD.md
- 저장 모델: docs/01_database_model.md
- HTTP 계약: docs/02_api_spec.md
- 시각 계약: docs/03_design_system.md
- 계층·모듈 경계: docs/04_backend_architecture.md, docs/05_frontend_architecture.md
- OpenAI 연동: docs/external/openai.md

docs/implementation/chatbot-plan.md의 멀티턴 설계는 현재 기준선으로 흡수한다. 다만 질문 실행 경로, context, 최대 turn, 도구, 프롬프트, 실행 이벤트는 이 문서가 우선한다. 기존 문서는 삭제하지 않고 Agent 구현 완료 후 대체됨을 명시한다.

### 1.1 유지할 기존 핵심 기능

- 텍스트 붙여넣기·txt·md·설정된 PDF 업로드 및 로컬 원문 저장
- 문서·청크·키워드·개념·별칭·관계 적재
- 문서 청킹 24,000자, overlap 500자, 원문 offset
- SQLite FTS5와 OpenAI Vector Store 의미 검색, local chunk mapping, FTS fallback
- 문서·청크·개념 3D graph, 필터·focus·노드 상세·원문 위치 이동
- 문서·분석 job·개념·질문·대화의 CRUD와 삭제 후 검색/그래프 제외
- 답변 근거 최대 3개, local source click 시 문서·청크 위치 이동
- 대화 기록·turn·rerun·삭제, dark/light theme, 접근성·반응형 UI

### 1.2 Agent 전환 범위

- 새 질문은 모두 Agent Orchestrator를 통과한다. 별도 legacy RAG 답변 경로를 병행하지 않는다.
- 기존 /questions와 /conversations/{id}/questions는 호환 adapter로 유지하되 내부에서는 Agent run을 생성한다.
- 도구는 search_knowledge, explore_node, OpenAI hosted web_search 세 가지로 고정한다.
- 도구는 읽기 전용이다. 문서 변경·삭제·외부 시스템 변경 tool은 추가하지 않는다.
- 대화 요약은 만들지 않는다. 현재 질문과 최근 완료 사용자 메시지 최대 3개 및 각각의 이어진 답변만 context에 넣는다.
- 최종 답변 전 LLM 호출·도구 실행을 반복하되 model cycle은 최대 30회다.
- 도구 실행과 탐색 내용은 순서형 event로 저장하고 프론트에 간략히 표시한다.

## 2. 문서와 구현 현황 대조

| 문서 | 현재 합의 | Agent 전환 시 보완 |
|---|---|---|
| PRD.md | 개인용 단일 사용자, 탐색 우선, 근거 우선, graph, AI 질문, 기록, P0~P5 | AI 질문을 Agent run으로 정의하고 tool activity·web source·30회 제한·중단 상태를 P0에 추가 |
| 01_database_model.md | documents/chunks/FTS/concepts/relations/jobs/conversations/questions/sources | agent_runs, agent_events, web source snapshot, 질문-실행 연결·cascade 추가 |
| 02_api_spec.md | 표준 envelope, async polling, conversation/question API | Agent 생성·조회·취소·SSE/replay와 activity/final citation DTO 추가 |
| 03_design_system.md | QuestionBar, ChatPanel, SourceCard, 상태·접근성 | AgentActivityTimeline, tool 상태·오류·max-turn·web citation 추가 |
| 04_backend_architecture.md | route-service-repository-integration, QuestionService, Retrieval/Responses gateway | Orchestrator·state machine·tool registry·prompt loader 추가; QuestionService는 facade로 축소 |
| 05_frontend_architecture.md | knowledgeApi, useKnowledgeController, ChatPanel, conversation 상태, polling | Agent run 상태·SSE reconnect·activity reducer 분리 |
| external/openai.md | Responses, Structured Outputs, Vector Store, local citation, store=False | function calling loop, hosted web_search, URL citation, strict schema 추가 |
| 03_design_system.md | Celestial Editorial, dark/light, graph 중심 layout, Agent activity | 탐색 event를 보조 정보로 노출하고 답변·근거를 주 콘텐츠로 유지 |
| implementation/chatbot-plan.md | 멀티턴 DB·context·source snapshot·rerun 계획 | 본 문서로 대체; 6 turn은 3 turn으로, 직접 RAG는 tool로 변경 |

### 2.1 현재 코드 기준선

- Backend: QuestionService.enqueue/process, ConversationContextService, RetrievalService, OpenAIResponsesGateway, ChatConversation, QuestionHistory, QuestionSource
- 질문 처리: POST /questions 또는 conversation 질문을 202로 등록하고 FastAPI BackgroundTasks에서 검색·답변 생성 후 polling
- 검색: Vector Store 결과를 document.vector_store_file_id와 chunk 내용으로 local mapping하고 실패 시 FTS/문자열 fallback
- 답변: local source를 S1~S3로 주입하고 citation marker를 검증한 뒤 source snapshot 저장
- no-evidence: 현재 general_answer와 AI generated document node를 만드는 별도 경로가 존재
- Frontend: knowledgeApi, useKnowledgeController, ChatPanel, QuestionHistoryPanel이 대화·turn을 polling으로 표시
- 실제 migration head: 20260731_0010_agent_schema_indexes. DB 문서의 이전 head 표기는 Agent migration과 함께 정정

### 2.2 현재 Agent 전환 결손

1. 모델이 tool을 선택하고 결과를 다시 받아 최종 답변까지 반복하는 실행기가 없다.
2. question 상태만 있고 run/cycle/tool call의 durable 상태와 재시작 복구 기준이 없다.
3. search_knowledge가 chunk node·문서·concept summary를 통합하는 독립 계약이 없다.
4. explore_node의 다중 node 조회, alias mention 위치, ±500자 문맥 병합이 없다.
5. hosted web_search와 URL citation 저장·표시 계약이 없다.
6. prompt가 responses.py 내부 문자열에 있고 system/tool prompt와 output schema가 분리되지 않았다.
7. 현재 6 turn context가 요구사항의 최근 3개 사용자 메시지와 불일치한다.
8. 프론트에 search/explore/web 순서형 activity, 취소, 30회 제한 UI가 없다.
9. BackgroundTasks가 실행 중 재시작·중복 실행·동시 turn을 durable하게 제어하지 못한다.

## 3. 확정 Agent 동작 계약

### 3.1 용어와 turn 계산

- Agent run: 사용자 한 질문의 전체 실행 단위. QuestionHistory turn과 1:1.
- Agent cycle: Responses API를 한 번 호출하는 단위. 최초 호출도 1회.
- Tool call: custom function 또는 hosted web search 실행 단위. cycle과 별도 집계.
- Activity: 사용자에게 표시할 safe progress event. raw model output이 아니다.

cycle 1~30에서 final message가 나오면 성공한다. 30번째 응답이 tool call이면 31번째 LLM 호출 없이 max_turns로 종료한다. 불완전 답변은 성공 답변으로 저장하지 않는다. MVP는 parallel_tool_calls=false로 한 cycle에 tool 하나만 실행한다.

### 3.2 Context 규칙

각 model 호출은 다음을 포함한다.

1. 외부 파일에서 읽은 versioned system prompt
2. 현재 사용자 질문
3. 최근 완료된 사용자 메시지 최대 3개와 각각의 완료 답변
4. 현재 run의 앞선 cycle output·tool call·tool output
5. 현재 cycle의 tool result

4번째 이전 turn은 전달하지 않고 summary도 생성하지 않는다. 대화 context와 현재 run trajectory는 구분한다. 문서·web result는 untrusted data로 표시하고 지시문으로 해석하지 않는다.

context_turn_count는 실제 이전 turn 수, context_truncated는 예산 때문에 잘린 경우에만 true다. 기존 6 turn 설정은 agent_context_turn_limit=3으로 교체한다.

### 3.3 답변 원칙

- 로컬 지식 근거가 필요하면 search_knowledge를 우선 사용한다.
- 개념 연결·문서 내 언급이 필요할 때만 explore_node를 사용한다.
- 최신성·외부 정보가 필요할 때만 hosted web_search를 사용한다.
- 근거가 없으면 없다고 말한다. 로컬 근거처럼 외부 사실을 위장하지 않는다.
- local citation은 S1~S3, web citation은 W1 이상으로 namespace를 분리한다.
- 최종 답변은 markdown과 검증된 citation metadata로 저장한다.

## 4. 목표 실행 구조

### 4.1 상태 machine

    queued
      → reasoning
      → tool_requested
      → tool_running
      → tool_succeeded / tool_failed
      → reasoning (반복)
      → completed

    reasoning/tool_running → canceled
    reasoning/tool_running → failed
    reasoning → max_turns

run 상태는 queued/running/completed/failed/canceled/max_turns, 현재 stage는 reasoning/tool_requested/tool_running/finalizing이다. 기존 question status는 API 호환을 위해 유지하되 Agent 상세 상태를 함께 반환한다.

### 4.2 Orchestrator 순서

1. 입력·conversation 검증
2. QuestionHistory와 AgentRun을 같은 transaction으로 생성
3. run-start event 기록, 최근 완료 turn 3개 조회
4. prompt loader로 markdown/json과 version 로드
5. Responses API를 tool_choice=auto, custom functions, hosted web_search, parallel_tool_calls=false로 호출
6. final message면 output contract·citation·길이 검증
7. custom function이면 schema 검증 후 registry handler 실행
8. hosted web search면 provider output과 URL citation 파싱
9. tool event 기록, safe tool output을 다음 호출에 주입
10. cycle를 증가시켜 반복
11. final answer·source snapshot·run terminal state를 commit
12. 예외·취소·max turn은 stable error와 terminal event 저장

provider의 숨은 conversation state에 의존하지 않는다. store=False와 로컬 trajectory를 기본으로 유지한다. SDK가 요구하는 response.output item은 다음 input에 보존하되 reasoning raw 내용은 사용자 화면과 로그에 노출하지 않는다.

### 4.3 응답 분기

| 응답 | 처리 |
|---|---|
| final message | contract 파싱, local/web citation 검증, 완료 |
| custom function_call | JSON 검증, registry handler, 다음 호출에 function_call_output |
| hosted web_search_call | 검색 activity, source metadata 저장, 다음 호출에 반영 |
| empty/unknown output | AGENT_OUTPUT_INVALID; repair cycle 1회 후 실패 |
| tool argument error | 필드별 원인을 tool output으로 전달하고 재시도 |

repair cycle도 30회에 포함한다.

## 5. Tool 설계

### 5.1 Registry

ToolRegistry는 이름, strict JSON Schema, handler, DTO, activity label formatter, timeout, retryable, max output, audit type을 가진다. Orchestrator는 if/elif로 tool을 분기하지 않는다.

공통 결과 envelope:

- ok
- tool
- data
- error: code, message, retryable, details, suggested_action
- truncated
- result_count

오류 message는 모델이 재시도할 수 있도록 원인·잘못된 필드·허용 범위·대안 action을 포함한다. stack trace·API key·SQL·절대 경로는 포함하지 않는다.

### 5.2 search_knowledge

입력은 query string 2~1,000자다. limit은 모델 schema에 노출하지 않거나 고정 3으로 제한한다.

처리:

1. RetrievalService.search(session, query, 3) 재사용
2. Vector Store 우선, local mapping 실패 시 FTS fallback
3. hit마다 chunk text, chunk node id, document snapshot, 연결 concept id·name·type·description 조립
4. 동일 문서의 다른 chunk는 별도 근거로 유지
5. 실제 사용 source는 QuestionSource snapshot으로 저장

반환:

- provider, candidate_count, mapping_failures, returned_count
- hits[]: citation_key S1~S3, chunk_node_id, chunk_id, document_id, document_title, document_status, chunk_text, start_char, end_char, score, mapping_confidence
- hits[].concepts[]: node_id, concept_type, canonical_name, english_name, abbreviation, description

chunk text는 server context 예산으로 제한하되 preview만 반환하지 않는다. event에는 query와 count만 기록한다.

### 5.3 explore_node

입력 node_ids는 1~8개다. 허용 형식은 document:<id>, chunk:<id>, concept:<id>이며 중복은 제거한다. 삭제·미존재 node는 항목별 오류로 반환하고 나머지는 계속 처리한다.

처리:

1. 대상 node 개요와 직접 연결 node 조회
2. concept이면 canonical 한글명·영문명·약어·별칭을 모두 검색
3. Unicode normalize와 casefold 후 연결 chunk에서 모든 mention 위치 검색
4. 위치별 앞뒤 500자 window 생성
5. 같은 chunk에서 겹치거나 인접한 window를 merge
6. offset, alias, merged start/end, excerpt 반환
7. node당 excerpt 12개, 전체 24KB 권장 상한

반환:

- nodes[]: id, name, type, description, source_count
- connections[]: source, target, relation_type, strength, evidence_chunk_id, target_summary
- mentions[]: node_id, chunk_node_id, document, matched_aliases, start/end, excerpt
- partial, truncated, skipped_node_ids

전체 graph를 반환하지 않고 GraphService와 같은 read repository를 사용한다.

### 5.4 web_search

OpenAI hosted tool을 사용하며 custom web search function으로 감싸지 않는다.

- Responses tools에 type web_search 등록
- tool_choice 기본 auto
- url_citation annotation에서 URL·title·위치·citation key 추출
- activity에는 sanitized query preview 표시
- 최종 web citation은 클릭 가능한 HTTPS URL
- 필요 시 include: ["web_search_call.action.sources"]로 source metadata 확보
- search_context_size는 low/medium/high 설정값이며 정확한 source 수를 보장하지 않음
- 현재 gpt-5.6-terra의 hosted web_search capability를 live smoke test로 검증. 미지원이면 OPENAI_AGENT_MODEL을 별도 설정하고 자동 임의 교체하지 않음

## 6. Prompt와 출력 계약

### 6.1 파일 구조

    backend/app/prompts/agent/
    ├─ system.md
    ├─ tool-policy.md
    ├─ tools/search_knowledge.md
    ├─ tools/explore_node.md
    ├─ tools/web_search.md
    ├─ tool-config.json
    └─ answer-contract.json

system.md는 제품 목적·근거·불확실성·context·언어·종료 규칙, tool-policy.md는 선택 기준·탐색량·data 경계를 정의한다. tool-config.json은 function schema와 제한, answer-contract.json은 final answer 구조를 정의한다.

PromptLoader는 startup 또는 첫 사용 시 파일 존재·JSON schema·version을 검증한다. prompt version과 model name을 AgentRun에 저장한다. 잘못된 prompt는 빈 문자열로 대체하지 않는다.

### 6.2 Injection 경계

사용자 질문·문서 청크·개념 개요·web 결과는 모두 untrusted data 구획으로 주입한다. data 안의 system/tool/ignore previous 문장은 명령으로 실행하지 않는다. web URL은 표시 데이터이며 추가 실행 지시가 아니다.

### 6.3 Final answer contract

필수 필드:

- answer_markdown
- local_citations[]: 실제 호출된 S1~S3 subset
- web_citations[]: 실제 반환된 W1.. subset
- related_node_ids[]: tool 결과에 존재하는 id만 허용
- stop_reason: completed/no_evidence/max_turns

backend는 contract와 실제 tool result를 대조한다. citation이 존재하지 않거나 수집되지 않은 source면 repair 또는 실패다. web만 사용하면 local source가 없음을 명시한다.

## 7. 저장 모델과 migration

### 7.1 기존 모델 재사용

ChatConversation, QuestionHistory, QuestionSource와 Document/Chunk/Concept/Alias/Relation read model을 유지한다. 기존 generated_document_id와 no-evidence AI 문서 생성은 과거 데이터·호환 API를 위해 유지하되 새 Agent 기본 흐름에서는 자동 문서 생성하지 않는다.

### 7.2 agent_runs

필드: id, conversation_id FK, question_history_id FK unique, status, stage, current_turn, max_turns snapshot 30, tool_call_count, model_name, prompt_version, stop_reason, last_error_code, last_error_message, started_at, completed_at, created_at, updated_at.

### 7.3 agent_events

필드: id, run_id FK, sequence run별 unique, turn, event_type, tool_name nullable, activity_label, input_safe_json, output_safe_json, error_code, duration_ms, created_at.

전체 원문·web payload·reasoning trace를 무제한 저장하지 않는다. local source는 QuestionSource, web source는 별도 snapshot table에 저장한다.

### 7.4 question_web_sources

필드: id, question_history_id FK, citation_key W1.. unique per question, url, title, publisher nullable, source_rank, created_at. HTTPS와 URL parser를 통과한 source만 표시한다.

### 7.5 무결성·복구

- conversation 삭제 시 run/event/web source/question source cascade 삭제
- rerun은 기존 turn 수정 없이 새 turn·run 생성
- queued/running run은 startup recovery에서 SERVICE_RESTARTED failed 또는 안전한 retry로 전환
- 같은 run의 sequence unique index
- migration은 20260730_0008 이후에 추가; 실제 revision은 20260731_0009_agent_runs_and_events와 20260731_0010_agent_schema_indexes

## 8. Backend 파일별 변경 계획

### 8.1 신규 파일

    backend/app/agent/
    ├─ orchestrator.py
    ├─ state.py
    ├─ contracts.py
    ├─ registry.py
    ├─ prompt_loader.py
    ├─ context.py
    ├─ errors.py
    └─ tools/
       ├─ base.py
       ├─ search_knowledge.py
       ├─ explore_node.py
       └─ web_search.py
    backend/app/prompts/agent/...
    backend/app/models/agent.py
    backend/app/schemas/agent.py
    backend/app/repositories/agent_runs.py
    backend/app/repositories/agent_events.py
    backend/app/services/node_exploration.py
    backend/app/integrations/openai/agent_responses.py
    backend/app/api/routes/agent_v1.py
    backend/alembic/versions/20260731_0009_agent_runs_and_events.py
    backend/alembic/versions/20260731_0010_agent_schema_indexes.py

### 8.2 기존 파일 수정

| 파일 | 변경 |
|---|---|
| app/core/config.py | OPENAI_AGENT_MODEL, max_turns=30, context=3, timeout/output/node limit, web search size |
| app/models/__init__.py | Agent model export |
| app/services/conversation_context.py | 최근 완료 turn 3개와 답변, summary/provider state 제거 |
| app/services/questions.py | 검색·답변 직접 실행 제거, Agent facade로 축소 |
| app/services/retrieval.py | tool용 통합 hit와 concept 연결 조회 |
| app/services/node_exploration.py | alias normalize, 모든 mention, ±500 merge, bounds |
| app/integrations/openai/responses.py | 문서 분석 유지; 직접 grounded/general/rewrite 호출은 Agent gateway로 대체 |
| app/integrations/openai/agent_responses.py | Responses create, function schema, hosted web_search, output/error normalize |
| app/api/routes/knowledge_v1.py | 기존 질문 route를 Agent adapter에 연결 |
| app/api/routes/agent_v1.py | run 생성·조회·SSE·cancel |
| app/schemas/common.py | AgentRun, AgentActivity, WebSource, Agent fields |
| app/main.py/startup | prompt validation, stale run recovery |
| app/core/errors.py | Agent/tool stable error codes |

route에서 OpenAI SDK를 직접 호출하지 않는다. route는 request/response와 task 등록만 담당한다.

### 8.3 QuestionService 책임 이동

유지: conversation 생성/조회, turn index, title, history/source DTO, rerun.

이동: context, retrieval query, evidence 전달, citation 검증, final state 전환은 Agent application service로 이동한다.

제거: no hits일 때 general_answer를 새 Agent 기본 분기로 사용하지 않는다.

호환: QuestionService.process(history_id)는 해당 history의 Agent run을 실행하는 adapter로 남길 수 있다.

## 9. API 설계 계획

### 9.1 Canonical API

POST /api/v1/agent/runs

Request: question 2~1,000자, conversation_id optional. conversation이 없으면 생성하고 QuestionHistory·AgentRun을 만든 뒤 background 실행한다.

202 data: run_id, question_id, conversation_id, turn_index, status=queued, stage=queued, current_turn=0, max_turns=30, created_at.

POST /api/v1/conversations/{conversation_id}/agent-runs

대화 지정형. active가 아니면 CONVERSATION_NOT_ACTIVE.

GET /api/v1/agent/runs/{run_id}

run status, stage, current turn, tool count, terminal error, final QuestionResult, local/web sources, related nodes를 반환한다.

GET /api/v1/agent/runs/{run_id}/events

SSE. Last-Event-ID 이후 event를 replay하고 새 event를 stream한다. 15초 heartbeat, terminal 후 종료. event는 sequence, run_id, turn, type, tool, label, status, query_preview, node_labels, result_count, error_code, created_at만 노출한다.

POST /api/v1/agent/runs/{run_id}/cancel

queued/running에 cancel을 기록한다. 실행 중 provider call은 boundary에서 중단하고 canceled로 종료한다. terminal이면 idempotent 현재 결과를 반환한다.

### 9.2 Legacy adapter

- POST /questions: Agent run 생성, 기존 202/polling 보존, data.agent_run 추가
- POST /conversations/{id}/questions: canonical conversation Agent API adapter
- GET /questions/{id}: 기존 QuestionResult에 agent summary와 web sources 추가
- GET /conversations/{id}: turn별 Agent summary만 포함; full event는 run endpoint
- rerun: 기존 history를 수정하지 않고 새 Agent run 생성

### 9.3 오류

기존 {data, meta, error} envelope를 유지한다. Agent error는 code, 사용자 message, retryable, request_id, run_id, details를 포함한다.

주요 code: AGENT_MAX_TURNS_EXCEEDED, TOOL_INPUT_INVALID, TOOL_EXECUTION_FAILED, DUPLICATE_TOOL_CALL, WEB_SEARCH_UNAVAILABLE, AGENT_OUTPUT_INVALID, AGENT_CANCELED, AGENT_BUSY.

## 10. Frontend 변경 계획

### 10.1 화면 계약

현재 ChatPanel의 답변·source 표시를 유지하고 답변 위에 bounded AgentActivityTimeline을 추가한다. MVP는 timeline 내부에서 item/status를 함께 렌더링하고 최근 activity를 노출한다.

고정 label 예시:

- RF 탐지 기술 관련 자료를 찾고 있습니다.
- 노드 탐색 중: RF 센서 · 전자전 · 대드론 통합체계
- 웹 검색 중: 2026 대드론 RF 탐지 조달, 투자 동향
- 답변을 정리하고 있습니다.

LLM 생성 문장을 label로 직접 표시하지 않는다. tool name과 sanitized query/node label을 backend 또는 typed formatter가 조합한다.

### 10.2 신규 파일

    frontend/src/api/agent.ts
    frontend/src/domain/agent.ts
    frontend/src/hooks/useAgentRunEvents.ts
    frontend/src/features/questions/AgentActivityTimeline.tsx
    frontend/src/features/questions/AgentActivityItem.tsx
    frontend/src/features/questions/AgentRunStatus.tsx
    frontend/src/features/questions/WebSourceCard.tsx

### 10.3 기존 파일

- api/knowledge.ts: 질문 생성은 Agent API adapter를 호출; 함수명은 단계적 유지
- domain/knowledge.ts: QuestionResult에 agent/web source 추가
- domain/agent.ts: run/status/stage/event/tool/web citation union
- useKnowledgeController.ts: Agent 상태를 별도 hook/reducer로 위임
- useAgentRunEvents.ts: SSE activity stream과 terminal close; canonical run polling은 useKnowledgeController가 담당
- ChatPanel.tsx: activity→answer, cancel/retry/max-turn
- QuestionHistoryPanel.tsx: run 상태와 실패/중단 이유
- SourceCard.tsx: local S#와 web W# 분리, web safe external link
- App.tsx/QuestionBar.tsx: 중복 전송 방지, cancel, 대화 전환
- styles: tool 색상은 의미 색상만 사용하고 답변 가독성 우선

프론트는 prompt/context를 조립하지 않는다. 최근 3 turn·tool 선택·citation 검증은 backend source of truth다.

### 10.4 접근성·상태

activity region은 aria-live=polite로 운영하고 heartbeat와 raw JSON은 읽히지 않게 한다. 실행 중 label·spinner·cancel을 제공한다. reduced motion에서는 graph/activity animation을 정적화한다. max turn·tool error·web failure는 텍스트·아이콘·action을 함께 표시한다. 모바일에서는 activity를 collapsible block으로 만든다.

## 11. 실행·복구·보안

### 11.1 BackgroundTasks

MVP는 FastAPI BackgroundTasks를 유지하되 task 시작 전에 DB run을 claim하고 heartbeat/terminal event를 저장한다.

- 동일 run은 한 프로세스만 claim
- startup에서 오래된 running을 SERVICE_RESTARTED failed로 정리
- task 예외는 run/history에 stable error 저장
- SSE disconnect 후 polling/reconnect 가능

다중 worker·긴 실행·동시 사용자 요구가 생기면 persistent worker/queue로 교체한다. Orchestrator public interface와 state contract는 유지한다.

### 11.2 Tool 안전성

- handler는 read-only session
- id·limit·query를 schema와 service 양쪽 검증
- tool timeout, 전체 deadline, output byte limit, 반복 call guard
- 문서/web는 data로 취급
- event에 API key·token·절대 경로·전체 원문 저장 금지
- web는 HTTPS와 정상 URL parser를 통과한 것만 표시

### 11.3 동시성

같은 conversation의 queued/running 질문은 기본 1개만 허용하고 다른 요청은 AGENT_BUSY로 거절한다. 다른 conversation은 독립 실행한다.

## 12. 단계별 구현 순서

### P0. 계약 고정·기준선

- 문서 head를 실제 0008과 정렬
- chatbot-plan의 6 turn·general answer를 전환 대상 표시
- status, 30 cycle, 최근 3 turn, tool schema, citation namespace 고정
- 기존 문서 분석·graph·CRUD·question regression 통과

완료: Agent 변경 전 baseline 재현.

### 12.1 각 Phase 공통 시작 게이트

각 Phase를 시작할 때 이미 알고 있는 내용도 다시 확인한다.

1. 해당 Phase와 관련된 PRD, DB, API, backend/frontend architecture, OpenAI reference 및 이 문서를 다시 읽는다.
2. 계획에 적힌 파일이 실제 존재하는지, 현재 branch의 최근 변경이 계획과 충돌하지 않는지 확인한다.
3. 관련 구현·테스트를 검색해 현재 상태, 이미 완료된 항목, 새로 생긴 결손을 기록한다.
4. 이전 Phase의 migration head, API DTO, 상태명, 환경변수와 실제 runtime을 대조한다.
5. 그 결과 계획과 달라진 부분을 먼저 문서에 반영한 뒤 해당 Phase 구현을 시작한다.
6. Phase 종료 시 문서 기준의 완료 조건, 테스트, 실제 요청/화면 흐름을 확인하고 다음 Phase로 이동한다.

문서와 코드가 충돌하면 임의로 한쪽을 무시하지 않고, 변경 이유와 영향 범위를 이 문서 및 관련 명세에 함께 반영한다.

### P1. 저장·prompt·tool contract

- agent_runs, agent_events, question_web_sources model/migration
- agent contracts/state/registry/errors
- prompt markdown/json와 loader
- search adapter, explore range merge, web citation DTO

완료: OpenAI 없이 fake session tool schema·bounds·error envelope 테스트 통과.

### P2. Responses Orchestrator

- Agent gateway와 tool definitions 연결
- direct final, search→final, search→explore→final, web→final
- error retry, max 30, duplicate, cancel, invalid final
- QuestionService를 Agent adapter로 전환
- run/event/history/source/web snapshot과 recovery

완료: fake Responses sequence가 모든 terminal state를 재현.

### P3. API·SSE·호환

- canonical run endpoint, detail, SSE replay, cancel
- 기존 question route 연결
- OpenAPI/error/no-store/CORS 확인
- Last-Event-ID와 terminal replay 확인

완료: 202→event/polling→final 답변 일관성.

### P4. Frontend Agent UX

- agent domain/api/event hook
- activity timeline, label, cancel, max-turn/error
- local/web source와 related node click
- history/rerun Agent API 전환
- theme·reduced motion·mobile·keyboard regression

완료: 사용자가 실행 순서를 보고 최종 근거를 열 수 있음.

### P5. 운영 품질·문서 정합성

- hosted web_search capability와 citation annotation live smoke test
- timeout/429/5xx/invalid output/restart/DB lock
- token·latency·tool output budget 측정
- PRD, DB, API, design, backend/frontend architecture, external/openai 갱신
- chatbot-plan 상단에 본 문서로 대체됨 표기

완료: 명세·구현·UI·테스트의 status, limit, endpoint, citation 규칙 일치.

## 13. 테스트와 수용 기준

### 13.1 Backend

- 최신 3 turn만 선택하고 답변과 chronological order로 조립
- cycle 30의 final 성공, 30번째 tool 요청의 max_turns 종료
- 동일 tool call 반복 차단
- function schema 오류와 tool timeout/429/5xx 정규화
- search 결과 3개 이하와 chunk/document/concept 통합
- 다중 node exploration, alias mention, overlap merge, offset 보존
- prompt 파일 누락·JSON invalid 감지
- migration cascade delete
- Agent 생성·polling·SSE replay·Last-Event-ID·cancel
- legacy question route의 Agent run 연결
- local S1~S3, web W1.. snapshot
- restart 후 stale run terminal 처리와 중복 방지
- API key 미설정 시 stable failure, secret 미노출

### 13.2 Frontend

- activity sequence 유지와 reconnect 중복 제거
- running/failed/canceled/max_turns/completed UI
- raw JSON·prompt·reasoning 미표시
- local source는 내부 panel, web source는 안전한 외부 링크
- 질문 취소·대화 전환 시 stale run이 현재 panel을 덮지 않음
- dark/light, keyboard, screen reader, reduced motion, 320px 이상

### 13.3 핵심 시나리오

1. RF 탐지 기술 질문이 search_knowledge를 실행하고 3개 local chunk·문서·concept를 답변에 사용
2. RF 센서와 전자전 관계 질문이 search 후 필요한 node만 explore_node로 탐색하고 mention excerpt 표시
3. 2026년 최신 조달 동향 질문이 web_search와 W citation 사용
4. tool 오류 후 Agent가 원인을 받고 재시도
5. 30회 내 답변 실패 시 부분 이력과 중단 사유 표시 후 정지
6. 4번째 이전 turn은 다음 호출에 포함되지 않고 summary도 생성되지 않음
7. 새로고침·SSE disconnect 후 DB event 순서로 복원

## 14. 추가 결정 사항과 권장안

### 14.1 Canonical endpoint

권장: /agent/runs를 새 표준으로 채택하고 /questions는 1~2 release 동안 adapter로 유지한다. 프론트는 P4부터 canonical API를 사용한다.

### 14.2 Agent model과 web capability

권장: OPENAI_AGENT_MODEL을 OPENAI_CHAT_MODEL과 분리하고 hosted web_search 지원 여부를 live smoke test로 확인한다. 미지원이면 설정 가능한 명시적 오류를 표시하고 자동 임의 교체하지 않는다.

### 14.3 Tool 병렬성

권장: MVP는 parallel_tool_calls=false. 순서형 activity, deterministic turn, 오류 재시도가 단순하다.

### 14.4 Provider state

권장: previous_response_id에 의존하지 않고 store=False와 로컬 trajectory를 사용한다. 재시작·재현·개인정보 삭제·테스트가 명확하다.

### 14.5 Event 저장 수준

권장: raw reasoning·전체 web payload는 저장하지 않고 bounded safe JSON만 저장한다. 출처는 snapshot table로 보존한다.

### 14.6 no-evidence와 AI 문서

권장: Agent 기본 흐름에서는 결과가 없다고 곧바로 AI 문서를 만들지 않는다. web_search 또는 명확한 근거 없음 답변을 우선한다. 기존 ai_generated document는 호환성을 위해 유지한다.

### 14.7 Worker

권장: 단일 사용자 local MVP는 durable DB state + BackgroundTasks로 시작한다. 다중 worker 요구가 생기면 queue worker로 교체하되 API·Orchestrator·event contract는 유지한다.

### 14.8 탐색 상한

권장 기본값: cycle당 tool 1개, explore_node 최대 8 node, node당 excerpt 12개, 전체 tool output 24KB, search 3개. 품질 근거 없이 제한을 늘리지 않는다.

## 15. 공식 OpenAI 계약 확인

구현자는 SDK 세부 문법을 바꾸기 전에 docs/external/openai.md와 다음 공식 문서를 확인한다.

- https://developers.openai.com/api/docs/guides/tools
- https://developers.openai.com/api/docs/guides/tools-web-search
- https://developers.openai.com/api/docs/guides/structured-outputs
- https://developers.openai.com/api/docs/guides/retrieval
- https://developers.openai.com/api/reference/resources/responses

## 16. 구현 반영 상태

- Backend: Agent 저장 모델·migration 0009/0010, 외부 prompt loader, tool registry, search/explore adapters, Responses gateway, 30-cycle orchestrator, Agent API/SSE/cancel, startup recovery 완료.
- Frontend: canonical `/agent/runs` 생성·조회·취소, SSE activity, run polling fallback, activity timeline, local/web source 표시 완료.
- 핵심 확인: Backend `11 passed`, Frontend `lint` 및 `build` 통과, Alembic `20260731_0010 (head)` 확인.
- 운영 전 확인: API key와 `OPENAI_AGENT_MODEL` 설정 후 hosted `web_search` citation live smoke test 필요.

신규 hosted tool 이름은 web_search를 사용한다. web citation annotation·source metadata·model capability는 실제 SDK 버전으로 contract test한다. OpenAI API 호출은 backend integration 경계 밖으로 노출하지 않는다.
