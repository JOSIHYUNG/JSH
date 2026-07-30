# JSH Second Brain Design Specification

- 문서 상태: Active visual direction / 2026-07-30
- 적용 대상: `frontend/` 전체 UI와 3D 지식 그래프
- 상위 기준: `docs/PRD.md`, `docs/03_design_system.md`
- 목적: 지식 탐색의 밀도와 원문·근거의 신뢰성을 유지하면서, 투박한 대시보드가 아닌 조용하고 몰입감 있는 개인 지식 작업 공간을 만든다.

## 1. 디자인 방향

### 1.1 컨셉: Celestial Editorial

`Celestial Editorial`은 우주 공간의 깊이와 편집 디자인의 명확한 읽기 순서를 결합한다.

- 배경: 순수 검정 대신 잉크 네이비와 은은한 별빛 그리드.
- 구조: 그래프는 넓은 canvas로 두고, 통계·최근 자료·상태는 작은 bento 카드로 분리한다.
- 타이포그래피: 제목은 큰 편집형 display, 본문은 높은 가독성의 sans-serif.
- 표면: 중요한 패널에만 반투명 material을 사용한다. 모든 카드에 blur/glass를 적용하지 않는다.
- 강조: teal을 주행동·AI, amber를 문서·근거, violet을 합성 답변에 사용한다.
- 모션: 그래프와 상태 변화의 의미를 강화하는 짧은 전환만 사용한다.

### 1.2 디자인 원칙

1. 그래프가 주인공이지만, 사용자가 다음 행동을 항상 알아볼 수 있어야 한다.
2. 장식보다 정보 계층을 먼저 만든다.
3. AI 결과는 답변보다 근거와 원문 이동 경로를 먼저 신뢰하게 만든다.
4. 색·blur·glow는 희소하게 사용하고 텍스트·아이콘·선 스타일로 의미를 중복 전달한다.
5. 모든 본문·버튼·상태 문구는 `text-sm` 이상을 유지한다.
6. 3D canvas는 접근성 보조 노드 목록과 동일한 정보를 제공한다.
7. 모바일에서는 그래프보다 질문·근거·원문 읽기를 우선한다.

## 2. 시각 언어

### 2.1 색상 토큰

```css
--canvas: #0D1726;
--canvas-raised: #142238;
--surface: #192A40;
--surface-raised: #223750;
--surface-glass: rgba(25, 42, 64, .78);
--surface-input: #101D31;
--text-strong: #F8FBFF;
--text-body: #C4D3E3;
--text-muted: #91A7BD;
--text-faint: #6F849A;
--teal: #78E8D8;
--teal-bright: #B6FFF3;
--amber: #F0B978;
--violet: #B4A4FF;
--success: #78DFA4;
--warning: #F4CA72;
--danger: #FF8798;
--line: rgba(184, 207, 229, .18);
--line-strong: rgba(184, 207, 229, .32);
```

사용 규칙:

- canvas와 surface의 명도 차이는 작게 유지하고, border·padding·타이포그래피로 영역을 나눈다.
- teal은 한 화면의 주요 action 1~2개와 AI 상태에만 사용한다.
- amber는 문서·출처·원문 위치, violet은 AI 답변·관계 강조에 사용한다.
- danger는 실패·삭제 확인에만 사용한다.
- 명도 대비는 본문과 주요 버튼 WCAG AA를 목표로 한다.

### 2.2 타이포그래피

```css
--font-sans: "Pretendard Variable", Pretendard, "Noto Sans KR", Inter, system-ui, sans-serif;
--font-display: "Newsreader", "Iowan Old Style", Georgia, serif;
```

| 토큰 | 크기 | weight | line-height | 용도 |
|---|---:|---:|---:|---|
| `text-sm` | 0.875rem | 400 | 1.55 | 모든 기본 UI·메타 최소값 |
| `text-md` | 1rem | 400 | 1.65 | 원문·답변·긴 설명 |
| `text-lg` | 1.125rem | 650 | 1.35 | 카드·섹션 제목 |
| `text-xl` | 1.375rem | 700 | 1.2 | 패널 제목 |
| `display-sm` | clamp(2.45rem, 4vw, 4.3rem) | 650 | 1.02 | 홈 hero |
| `display-md` | clamp(2rem, 4vw, 3.5rem) | 650 | 1.0 | 결과·상세 강조 |

- 한글 본문은 display serif를 사용하지 않는다.
- hero와 핵심 숫자에만 display serif를 사용하고, 입력·버튼·상태는 sans-serif로 고정한다.
- 숫자에는 `font-variant-numeric: tabular-nums`를 사용한다.
- 긴 원문은 68~78ch, line-height 1.75로 제한한다.

### 2.3 형태·간격

| 토큰 | 값 |
|---|---:|
| `space-1` | 4px |
| `space-2` | 8px |
| `space-3` | 12px |
| `space-4` | 16px |
| `space-5` | 20px |
| `space-6` | 24px |
| `space-8` | 32px |
| `space-10` | 40px |
| `radius-sm` | 8px |
| `radius-md` | 14px |
| `radius-lg` | 24px |
| `radius-pill` | 999px |

- primary card는 `radius-lg`, control은 `radius-md`, badge는 pill을 사용한다.
- shadow보다 1px border, 내부 하이라이트, 낮은 강도의 glow를 우선한다.
- 화면의 주요 정렬 기준은 8px grid다.

## 3. 레이아웃

### 3.1 Desktop 1200px 이상

```text
┌──────────────────────────────────────────────────────────┐
│ Brand                         status  history  add source │
│                    hero statement / intro                 │
│              AI question command surface                   │
│  docs  nodes  links          knowledge graph                │
│  ┌───────────────────────────────┐ ┌────────────────────┐ │
│  │ 3D canvas + graph controls     │ │ recent / signal   │ │
│  └───────────────────────────────┘ └────────────────────┘ │
│ footer                                                     │
└──────────────────────────────────────────────────────────┘
```

- content max width: 1480px, page padding: 32~56px.
- graph는 첫 화면의 가장 큰 surface로 둔다.
- stat strip은 그래프와 분리된 horizontal bento rail이다.
- context panel은 400~520px drawer이며 canvas 위를 덮되 원래 화면 맥락을 유지한다.
- 질문창은 hero 아래에 sticky가 가능하지만 원문 패널을 가리지 않는다.

### 3.2 Tablet 768~1199px

- page padding 24px.
- bento rail은 2열로 재배치한다.
- context panel은 right drawer, graph는 최소 480px 높이를 유지한다.
- filter는 한 줄 wrap 가능한 control group으로 만든다.

### 3.3 Mobile 320~767px

- page padding 16px.
- hero는 display-sm, graph는 360~440px로 축소한다.
- 그래프 아래에 항상 node list를 표시한다.
- context panel은 full-screen sheet로 전환한다.
- hover 정보를 tap·node list로 대체한다.
- 질문창의 submit button은 입력 아래 full width로 배치한다.

## 4. 화면별 명세

### 4.1 Home / Knowledge Space

순서: brand → hero → AI question → stats → graph → recent/signal → footer.

- hero의 첫 문장은 서비스의 가치, 둘째 문장은 개인 지식 우주를 표현한다.
- stat는 `자료`, `노드`, `연결`만 보여주고 장식용 숫자를 추가하지 않는다.
- graph header에 `CONSTELLATION / KNOWLEDGE MAP`, 현재 적용 필터, 일부 표시 상태를 함께 표시한다.
- empty state는 그래프 대신 자료 추가 action을 중심으로 보여준다.

### 4.2 Question Command Surface

- label: `내 지식에게 질문하세요`.
- placeholder: `키워드나 문장으로 물어보세요`.
- primary action: `AI에게 질문`.
- loading 단계: `관련 자료를 찾는 중…` → `근거를 바탕으로 정리 중…`.
- 질문 결과는 drawer로 열고 입력창은 유지한다.

### 4.3 Graph Surface

- document: rounded rectangle + amber.
- concept: circle + type color.
- chunk: 낮은 opacity의 작은 node, 기본 숨김.
- selected: outer ring, related links만 high opacity.
- link strength는 width와 opacity로만 표현하고 particle은 저강도로 제한한다.
- reset, fit, filters, node list는 canvas 밖의 일반 HTML control로 제공한다.

### 4.4 Context Drawer

공통: entity badge, 제목, 상태, close, `그래프에서 중심`.

- 문서: summary → keywords → concepts → original/chunks → edit/reanalyze/delete.
- 개념: canonical/English/abbreviation → aliases → source chunks → related concepts.
- 질문: answer → citation markers → source cards → related concepts → retry/edit.
- source click은 drawer를 닫지 않고 document detail로 교체하며 source chunk 위치를 강조한다.

### 4.5 Add Document Modal

상태: `idle → validating → processing → completed | failed | canceled`.

- 입력 화면과 처리 화면의 visual center를 유지한다.
- progress는 실제 backend job stage를 표시한다. 가짜 timer로 단계를 진전시키지 않는다.
- 완료 화면은 제목·요약·개념 수·관계 수·그래프 이동 action을 보여준다.
- 실패 화면은 원문 보존, 실패 원인, 재시도 action을 함께 보여준다.

## 5. 컴포넌트 계약

| 컴포넌트 | 필수 상태/행동 |
|---|---|
| `TopBar` | home, add, history, system status, theme toggle |
| `QuestionBar` | empty, active, loading, error, prefilled |
| `KnowledgeGraph` | loading, empty, ready, truncated, selected, reduced-motion |
| `GraphControls` | type, node layer, recent period, strength, reset, fit |
| `RecentDocuments` | empty, processing, ready, failed, open |
| `DocumentPanel` | detail, source highlight, reanalyze, delete, center |
| `ConceptPanel` | aliases, sources, related, ask, center |
| `QuestionResultPanel` | answer, citations, no evidence, retry, edit |
| `QuestionHistoryPanel` | list, restore, rerun, item delete, empty |
| `AddDocumentModal` | validate, progress, completed, failed, cancel |

## 6. Motion

- hover/focus: 140~180ms.
- drawer/modal: 220~280ms ease-out.
- graph fit: 650~850ms.
- background glow: 8~14s, low opacity.
- loading spinner/orbit는 상태 전달에만 사용한다.
- `prefers-reduced-motion: reduce`에서 transform·particle·glow animation을 제거한다.
- blur는 panel backdrop과 hero atmospheric layer에만 사용한다.

## 7. 접근성

- 본문·버튼·입력·상태 문구는 14px 미만으로 만들지 않는다.
- icon-only control에는 accessible name을 준다.
- focus-visible은 2px teal outline + 3px offset.
- modal은 Escape, backdrop close, focus return을 지원한다.
- graph canvas는 node list로 동일한 entity를 keyboard 접근 가능하게 한다.
- 색상만으로 concept type·status·source rank를 전달하지 않는다.
- 비동기 상태는 `aria-live="polite"`, 실패는 action과 함께 inline으로 표시한다.

## 8. 구현 규칙

- 신규 semantic 색상은 `tokens.css` 토큰을 우선 사용한다. 기존 graph/vendor 색상과 투명도 표현은 feature CSS에서 token 기반 rgba로 제한한다.
- primitive는 시각적 variant를 책임지고 feature는 업무 상태를 책임진다.
- CSS class는 semantic 영역명(`graph-section`, `context-panel`)을 사용한다.
- 데이터 없는 screenshot 전용 장식·fake preview·demo text를 코드에 추가하지 않는다.
- 3D graph의 성능 개선을 위해 canvas 효과보다 DOM node list와 filter를 우선한다.

## 9. Visual QA

필수 viewport: 1440×900, 1280×800, 768×1024, 390×844.

검증 항목:

- 첫 화면에서 질문·자료 추가·그래프 조작을 2단계 이내에 찾을 수 있다.
- 3D canvas가 통계·질문창을 덮지 않는다.
- panel open 시 제목과 close action이 항상 보인다.
- source click이 document panel과 원문 위치 강조로 이어진다.
- loading/empty/error 상태가 레이아웃을 흔들지 않는다.
- dark surface 위 본문과 버튼 대비가 유지된다.
- reduced motion에서 읽기와 조작이 동일하게 가능하다.

## 10. 릴리스 적용 순서

1. P0 완료: tokens, typography, home hierarchy, graph surface, question surface, drawer baseline.
2. P1 완료: 실제 분석 진행률, source range highlight, reanalyze/delete, error/empty states.
3. P2 완료: graph focus, 고급 필터, 질문 이력 재실행·삭제, source snapshot states.
4. P3 예정: concept/relation 수동 큐레이션, URL 상태 복원, 삭제 실행 취소.
5. P4 예정: focus trap, 자동 접근성·시각 회귀, 대형 그래프 성능 예산.
6. P5 예정: export/import, collections, saved views, personalization.

참고: [Material 3](https://m3.material.io/), [Apple Materials HIG](https://developer.apple.com/design/human-interface-guidelines/materials), [Apple Foundations HIG](https://developer.apple.com/design/human-interface-guidelines/foundations).

## 11. 테마 시스템

### 11.1 목표

OS 테마 선호를 최초 기본값으로 사용하고, 밝아진 `Celestial Editorial` 다크 테마와 장시간 문서 읽기에 적합한 라이트 테마를 동등하게 제공한다. 테마는 색상 토큰만 교체하며 정보 구조·레이아웃·컴포넌트 의미는 동일하게 유지한다.

### 11.2 테마 상태

| 상태 | 기준 | 저장 |
|---|---|---|
| `dark` | 밝은 청회색 표면 위에 우주·teal glow를 사용하는 어두운 모드 | `localStorage[jsh-theme]` |
| `light` | 백색·청회색 표면과 낮은 농도의 대기 효과를 사용하는 읽기 모드 | `localStorage[jsh-theme]` |

- 저장된 값이 없으면 `prefers-color-scheme` 결과를 최초 기본값으로 사용한다.
- 사용자가 선택한 모드는 다음 방문에도 복원한다.
- 테마 전환은 페이지 reload 없이 즉시 적용한다.
- `html[data-theme]`와 `color-scheme`을 함께 갱신해 native input/select와 스크롤바도 같은 모드로 맞춘다.
- 전환 버튼은 TopBar에 두며 현재 모드와 전환될 모드를 아이콘·텍스트·accessible name으로 함께 전달한다.

### 11.3 색상 방향

다크 테마는 기존의 거의 검은 남색 대신 `#0D1726` canvas, `#142238` raised canvas, `#192A40` panel을 사용한다. 배경과 카드의 명도 차이를 유지하되 텍스트와 graph node가 묻히지 않도록 surface 대비를 높인다.

라이트 테마는 `#F3F7FB` canvas, `#E9F0F6` raised canvas, `#FFFFFF` panel을 사용한다. 본문은 짙은 청색, 보조 텍스트는 청회색으로 두고 teal은 primary action·graph link·focus, amber는 문서·근거, violet은 AI 답변에 한정한다.

### 11.4 컴포넌트 규칙

- 3D graph의 WebGL background는 테마에 따라 dark `#0D1726`, light `#E9F0F6`로 바꾼다.
- 다크 모드의 glow와 grid는 낮은 불투명도로 유지한다. 라이트 모드에서는 glow를 줄이고 얇은 청회색 grid를 사용한다.
- 카드·drawer·modal은 라이트 모드에서 흰색 surface와 1px border를 우선하며 과도한 shadow나 blur를 사용하지 않는다.
- input/select는 테마별 `surface-input`을 사용해 본문 배경과 구분한다.
- 상태·분류는 색상만으로 전달하지 않고 기존의 label, badge, icon을 함께 표시한다.
- 라이트 모드에서도 teal·amber·violet 텍스트는 WCAG AA 대비를 만족하는 어두운 variant를 사용한다.

### 11.5 수용 기준

- TopBar에서 한 번의 조작으로 두 테마를 전환할 수 있다.
- 새로고침 후 마지막 테마가 복원된다.
- 3D graph, toolbar, 질문 입력, 카드, drawer, modal이 모두 선택된 테마의 surface와 text token을 사용한다.
- 라이트 모드에서 본문·입력·버튼·근거 highlight를 읽을 수 있고, 다크 모드에서 graph node와 link가 배경에 묻히지 않는다.
- `prefers-reduced-motion` 환경에서 테마 전환과 graph fit은 기능을 유지하되 불필요한 애니메이션을 줄인다.
