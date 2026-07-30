# 03. Design System

- 문서 상태: Reviewed / token baseline
- 시각 방향의 canonical spec: `docs/design.md`
- 기준 문서: `docs/PRD.md`
- 대상: 개인용 지식 탐색 서비스, desktop-first
- 핵심 언어: 밝고 깊이감 있는 지식 우주·기술적·조용한 집중·근거가 보이는 탐색

## 1. 디자인 목표

1. 3D 그래프의 인상은 강하게, 문서 읽기와 근거 확인은 더 명확하게 한다.
2. 한 화면에서 `지식 구조 → AI에게 질문 → 근거 → 원문`이 끊기지 않게 한다.
3. 자동 분석의 불확실성을 색·배지·문구로 숨기지 않는다.
4. 단일 사용자 MVP의 속도를 위해 화면 수를 늘리지 않고, 홈·모달·상세 패널·질문 기록으로 상태를 수렴한다.
5. 본문·버튼·상태 텍스트 모두 PRD의 최소 `text-sm` 이상을 지킨다.

## 2. 정보 구조

```text
App shell
├─ Top bar: brand / 자료 추가 / 질문 기록 / system status
├─ Question bar: one input + AI에게 질문
├─ Knowledge graph: document + concept default
├─ Utility rail: recent documents / recent questions / filters
└─ Context panel
   ├─ Document detail
   ├─ Concept detail
   ├─ Question result + sources
   └─ Empty/error/status state
```

단일 진입 원칙:

- 사용자에게 `검색` 버튼·검색 모드를 보여주지 않는다.
- 키워드·문장도 `AI에게 질문` 입력으로 제출한다.
- 관련 자료 검색은 결과 화면의 근거 영역 안에서 자동으로 표현한다.

## 3. 디자인 토큰

토큰은 CSS variable 또는 TypeScript theme object로 구현하되, 컴포넌트는 raw hex를 직접 사용하지 않는다.

### 3.1 색상

#### Surface

| 토큰 | 값 | 용도 |
|---|---|---|
| `surface.canvas` | `#0D1726` | 전체 배경, 그래프 공간 |
| `surface.canvas-alt` | `#142238` | section 구분 |
| `surface.panel` | `#192A40` | 카드·패널 |
| `surface.panel-raised` | `#223750` | hover·선택 패널 |
| `surface.overlay` | `rgba(4, 10, 18, .82)` | modal backdrop |
| `surface.input` | `#101D31` | 입력 배경 |
| `surface.disabled` | `#1B2A3A` | disabled |

#### Text

| 토큰 | 값 | 대비 목적 |
|---|---|---|
| `text.primary` | `#F6F9FC` | 제목·본문 |
| `text.secondary` | `#C9D6E4` | 보조 설명 |
| `text.muted` | `#91A3B8` | 메타데이터 |
| `text.inverse` | `#07111E` | accent 위 text |
| `text.link` | `#7BE2D4` | 원문 이동·관련 link |

#### Accent / Semantic

| 토큰 | 값 | 용도 |
|---|---|---|
| `accent.teal` | `#72DFCF` | AI 질문, concept, primary action |
| `accent.amber` | `#F2BD7C` | document, highlight, caution |
| `accent.violet` | `#B8A8FF` | relation, secondary emphasis |
| `semantic.success` | `#7BE2A8` | completed/ready |
| `semantic.info` | `#6CA8FF` | processing/status |
| `semantic.warning` | `#F5CF79` | low confidence/partial |
| `semantic.danger` | `#FF8D9D` | failed/delete |
| `border.default` | `rgba(172, 215, 236, .16)` | 일반 경계 |
| `border.focus` | `#73D6C8` | keyboard focus |

컬러 사용 규칙:

- 색만으로 상태를 구분하지 않는다. label/icon/text를 함께 사용한다.
- `semantic.danger`는 삭제 확정·실패 행동에만 사용하고 그래프 장식에는 사용하지 않는다.
- 그래프 색상은 `color_token` metadata로 받고 프론트가 token map에서 선택한다.

라이트 테마 override:

| 역할 | 값 |
|---|---|
| canvas / canvas-alt | `#F3F7FB` / `#E9F0F6` |
| panel / panel-raised / input | `#FFFFFF` / `#F8FBFD` / `#F8FBFD` |
| text primary / secondary / muted | `#102237` / `#40566D` / `#6B7F94` |
| teal / amber / violet | `#168C83` / `#B76724` / `#6653C7` |
| success / warning / danger | `#147A4F` / `#976100` / `#B5304A` |

- 저장된 테마가 없으면 OS 선호를 사용하고, 선택값은 local storage에 보존한다.
- 두 테마에서 semantic 의미와 graph node 유형은 바꾸지 않고 명도·채도만 조정한다.
- 3D canvas 배경과 node/link palette도 테마 전환 즉시 함께 갱신한다.

### 3.2 개념 유형 색상

13개 유형은 색상만으로 구분하지 않고 아이콘/short label을 병행한다. 기본 palette는 인접 유형 간 명도 차이를 확보한다.

| 유형 | token | 시각 의미 |
|---|---|---|
| organization | `graph.org` | amber 계열 |
| organization_unit | `graph.org-unit` | amber-light |
| person | `graph.person` | violet |
| country | `graph.country` | blue |
| region | `graph.region` | blue-light |
| place | `graph.place` | cyan |
| technology | `graph.tech` | teal |
| equipment | `graph.equipment` | orange |
| system | `graph.system` | indigo |
| project_program | `graph.project` | magenta |
| policy_law | `graph.policy` | green |
| event | `graph.event` | red-orange |
| document | `graph.document` | amber |

Graph node rules:

- document: 둥근 사각형/amber glow.
- concept: 원형/유형 색.
- chunk: 작고 낮은 opacity; 기본 숨김.
- selected node: 2px outer ring + related edge emphasis.
- low-confidence relation: 점선·particle 없음.

### 3.3 Typography

기본 system sans를 사용하고 긴 원문에는 읽기 좋은 line-height를 적용한다. 제품명/eyebrow만 display treatment를 허용한다.

| token | size | weight | line-height | 용도 |
|---|---:|---:|---:|---|
| `text-xs` | 0.75rem | 500 | 1.4 | 최소 메타; 본문 사용 금지 |
| `text-sm` | 0.875rem | 400 | 1.55 | 기본 UI/body 최소 |
| `text-md` | 1rem | 400 | 1.6 | 원문/답변 |
| `text-lg` | 1.125rem | 600 | 1.4 | card heading |
| `text-xl` | 1.25rem | 700 | 1.3 | panel title |
| `display-sm` | 2rem | 700 | 1.1 | home hero |
| `display-lg` | 3rem | 700 | 1.0 | desktop hero 제한 |

- 본문·원문·질문·답변은 `text-sm` 미만을 사용하지 않는다.
- 원문은 65~78자 정도의 읽기 폭, line-height 1.7, paragraph gap 1rem.
- 숫자 통계에는 tabular numeral을 사용한다.

### 3.4 Spacing / radius / elevation

| token | 값 |
|---|---:|
| `space-1` | 4px |
| `space-2` | 8px |
| `space-3` | 12px |
| `space-4` | 16px |
| `space-5` | 20px |
| `space-6` | 24px |
| `space-8` | 32px |
| `space-10` | 40px |
| `radius-sm` | 6px |
| `radius-md` | 10px |
| `radius-lg` | 16px |
| `radius-pill` | 999px |

- 카드 내부 기본 padding 20~24px.
- clickable element 간 gap 최소 8px.
- shadow보다 1px border와 subtle glow를 우선한다.
- modal z-index는 graph/control보다 높고 toast보다 낮다.

## 4. 컴포넌트 계약

### 4.1 AppShell

구성: `TopBar`, `QuestionBar`, `KnowledgeGraph`, `UtilityRail`, `ContextPanel`, `ToastRegion`.

상태:

- normal: 그래프 중심.
- panel-open: 그래프 폭을 줄이고 panel을 고정.
- modal-open: backdrop으로 배경 interaction 차단.
- global-busy: 진행 중인 영역만 disabled; 자료 추가와 질문을 모두 막을지 작업별로 결정.

### 4.2 TopBar

- brand는 link가 아니라 home reset action.
- `자료 추가`는 primary/teal.
- `질문 기록`은 secondary.
- theme toggle은 현재 상태가 아니라 전환 결과를 accessible name으로 제공한다.
- status indicator는 `AI 연결됨`, `로컬 모드`, `로컬 저장소 점검 필요`, `상태 확인 중`으로 텍스트 표시.
- 좁은 화면에서는 status를 icon+tooltip으로 축약하되 accessible name을 유지한다.

### 4.3 QuestionBar

- placeholder: `내 지식에 대해 질문하세요. 키워드나 문장도 좋아요.`
- single text input, submit label `AI에게 질문`.
- 2자 미만은 submit disabled가 아니라 helper text로 이유를 표시한다.
- 제출 중에는 button label `관련 자료를 찾는 중…` → `답변을 만드는 중…`으로 stage를 반영한다.
- 답변 오류 후 입력값은 보존하고 `다시 시도`를 노출한다.
- history에서 복원된 질문은 badge `기록에서 불러옴`을 표시한다.

### 4.4 KnowledgeGraph

필수 control:

- rotate / zoom / pan / reset / fit / focus selected.
- filter: concept type, recent days, node type, min strength.
- legend: document/chunk/concept + 13 types.

interaction:

- hover: label, type, connection count.
- click: ContextPanel open; keyboard focus는 별도 node list에서 지원.
- double click은 사용하지 않는다.
- selected node 주변만 edge를 강조하고 나머지는 opacity를 낮춘다.
- 빈 graph는 canvas 대신 empty state를 보여준다.
- limit으로 일부만 나온 graph에는 `일부 관계만 표시 중` 배지를 표시한다.

### 4.5 ContextPanel

폭: desktop 360~480px, mobile full width.

공통 header:

- entity type badge
- title
- close
- `그래프에서 중심에 놓기`

Document panel:

- title, source file, status, summary, keywords, original open, chunk list, linked concepts, reanalyze/delete.
- evidence로 들어오면 해당 chunk에 자동 scroll·highlight.

Concept panel:

- canonical name, English name, abbreviation, type, description.
- aliases, source chunks, linked documents, related concepts.
- `이 개념으로 질문`은 QuestionBar에 값을 채우고 사용자가 submit한다.

Question result panel:

- question, status, answer markdown, `[S1]` citation link, source cards, related concepts.
- source card click은 panel을 닫지 않고 document detail을 replace/open한다.
- stale source는 `당시 근거` badge와 `현재 문서에서 열 수 없음`을 표시한다.

### 4.6 AddDocumentModal

모달은 상태 machine을 사용한다.

| 상태 | 사용자 행동 | 화면 |
|---|---|---|
| `idle` | paste/upload 선택 | source tabs, title, input |
| `validating` | 입력 수정 불가 | validation message |
| `processing` | cancel/close | stepper, progress; P1에서 live preview 추가 |
| `completed` | graph/document/undo | result summary |
| `failed` | retry/keep draft/close | error reason + next action |
| `canceled` | resume/retry/close | original retained notice |

입력:

- paste: title optional + multiline textarea.
- upload: `.txt`, `.md` P0; configured PDF support only when enabled.
- external processing notice는 submit action 위에 배치한다.
- title 자동 제안은 editable input으로 제공한다.

분석 preview(P1 목표):

- 단계: 원문 저장, 청크, 요약/키워드, concepts, relations, 로컬 complete. 전체 원문 AI index는 로컬 완료 후 별도 상태로 동기화.
- concept row는 type badge + canonical name + `새 개념/기존 연결/유사 후보` 상태.
- preview event가 구현되면 부분 결과에 `아직 저장 중`을 명시한다. 현재 runtime은 stage/progress만 표시한다.

### 4.7 SourceCard

필드: citation key, document title, chunk preview, score, chunk position, openable/stale.

- source rank 1~3을 강제 표시.
- 같은 문서 여러 청크는 카드 안에서 묶을 수 있지만 citation key는 유지한다.
- 카드 안의 score 숫자만으로 품질을 단정하지 않고 `관련도` label을 사용한다.

### 4.8 StatusBadge / Toast / ErrorState

모든 상태는 color + icon + text + action의 조합이다.

| 상태 | badge | action |
|---|---|---|
| ready | `준비됨` | 열기 |
| processing | `분석 중` | 진행 보기 |
| failed | `분석 실패` | 다시 시도 |
| no evidence | `근거 없음` | 질문 수정/자료 추가 |
| partial | `근거 부족` | 원문 확인 |
| stale | `당시 근거` | 현재 문서 상태 확인 |
| deleting | `삭제 중` | 닫기 |

Toast는 성공·일반 오류의 짧은 안내에만 사용한다. 분석 단계·근거 부족·삭제 영향은 panel/inline error로 남긴다.

## 5. Layout / responsive

### Desktop >= 1200px

- max content width 1440px.
- graph는 main 영역 60~70%, panel은 360~480px.
- graph height 최소 540px.
- question bar는 top area에 sticky 가능하나 원문 읽기 중 시야를 가리지 않는다.

### Tablet 768~1199px

- utility rail을 collapsible로 줄인다.
- panel은 overlay drawer.
- graph height 420~540px.

### Mobile < 768px

- desktop-first; graph는 축소 탐색, rotate/zoom control을 명시한다.
- question bar와 answer/source/document reading을 우선한다.
- panel은 bottom sheet/full screen.
- hover에 의존하는 정보는 tap 또는 node list로 대체한다.

## 6. Motion

- 기본 motion duration 160~240ms.
- graph particle animation은 관계 이해에 필요한 경우만 사용하고, 낮은 강도로 시작한다.
- 분석 progress는 단계 변화에만 transition을 적용한다.
- `prefers-reduced-motion: reduce`에서는 particle, glow pulse, panel slide를 제거하고 opacity transition만 사용한다.
- motion이 질문 submit·원문 읽기·근거 클릭을 지연시키지 않는다.

## 7. Accessibility

- 모든 icon-only button에 accessible name.
- focus-visible outline은 `border.focus` 2px, 배경과 충분한 대비.
- modal open 시 focus trap, Escape 닫기, 닫힌 뒤 trigger 복귀.
- graph는 canvas만으로 완료하지 않는다. 선택 가능한 `그래프 노드 목록`을 panel의 접근성 fallback으로 제공한다.
- node color와 edge style은 text/type/line style과 중복 표현.
- keyboard order: topbar → question → graph controls → utility → panel.
- error는 `aria-live=polite`, 완료/실패는 assertive가 필요한 경우에만 사용.
- 원문 강조는 색뿐 아니라 left border·background·citation badge로 표시.

## 8. Content guidelines

- 버튼은 동작 중심: `AI에게 질문`, `자료 추가`, `그래프에서 보기`, `원문 열기`, `다시 시도`.
- 기술 용어 대신 사용자 문구: `Vector Store`는 설정/진단에서만, 화면에는 `AI 검색 인덱스`.
- 답변 부족: `관련 자료가 충분하지 않아 단정해서 답할 수 없습니다.`
- AI 장애: `자료는 보존되었습니다. 잠시 후 다시 시도해 주세요.`
- 삭제: `이 자료는 그래프와 새로운 AI 답변에서 즉시 제외됩니다.`
- 길이·제한 오류는 사용자가 수정할 수 있는 방법을 함께 말한다.

## 9. Visual QA 기준

- 1440×900, 1280×800, 768×1024, 390×844에서 overflow 없음.
- 다크·라이트 배경 위 text.primary/secondary가 WCAG AA 수준의 대비를 갖는다.
- graph node label이 panel·question bar를 덮지 않는다.
- 답변 citation click → source card → document chunk highlight가 한 번의 명확한 transition으로 이어진다.
- processing/failed/no evidence/stale/empty 상태는 production mock 없이 격리된 test fixture 또는 component harness에서 재현 가능해야 한다.
- 고밀도 graph에서 node를 찾기 위한 filter와 focus action이 항상 노출된다.

## 10. Component acceptance checklist

- [x] 모든 primary action이 `AI에게 질문` 단일 흐름과 일치한다.
- [x] document/chunk/concept 상태와 디자인 token mapping이 API enum과 일치한다.
- [x] source card가 rank·citation·openable/stale를 모두 표현한다.
- [x] 3D graph fallback node list가 있다.
- [ ] modal close/cancel/retry는 분리됨. 완료 직후 실행 취소(undo)는 P2.
- [x] reduced motion과 keyboard node-list navigation을 구현했다. 실제 브라우저 접근성 회귀는 P4.
