# Local MCP Server 설정

## 역할

`second-brain`은 프로젝트의 기존 Agent 도구를 재사용하는 로컬 STDIO MCP 서버다.

- `search_knowledge(query)`: SQLite FTS5/OpenAI Vector Store 기반 검색 결과와 문서·청크·연결 개념 반환
- `explore_node(node_ids)`: 기존 그래프 연결·원문 언급 구간 탐색 결과 반환
- 두 Tool 모두 `readOnlyHint=true`, 변경·삭제 작업 없음
- MCP 구현 위치: `backend/app/mcp/server.py`

## 의존성 설치

Backend 가상환경에서 실행한다.

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -e .
```

`pyproject.toml`의 `mcp>=2,<3`가 Python MCP SDK 의존성이다.

## 직접 실행

프로젝트 루트에서 실행한다. STDIO 프로토콜을 사용하므로 터미널에 일반 로그를 출력하지 않고 MCP 클라이언트의 실행을 기다린다.

```powershell
backend\.venv\Scripts\python.exe backend\app\mcp\server.py
```

## Codex 등록

최초 등록:

```powershell
codex mcp add second-brain -- "C:\Users\KHP-17\Downloads\JSH\backend\.venv\Scripts\python.exe" "C:\Users\KHP-17\Downloads\JSH\backend\app\mcp\server.py"
```

등록 확인:

```powershell
codex mcp list
codex mcp get second-brain
```

정상 상태는 `second-brain`, `transport: stdio`, `enabled: true`다. 로컬 STDIO 서버이므로 인증 상태는 사용하지 않는다.

## 재등록

실행 경로·가상환경·서버 파일 위치를 변경했거나 설정을 갱신할 때 사용한다.

```powershell
codex mcp remove second-brain
codex mcp add second-brain -- "C:\Users\KHP-17\Downloads\JSH\backend\.venv\Scripts\python.exe" "C:\Users\KHP-17\Downloads\JSH\backend\app\mcp\server.py"
codex mcp list
```

Codex가 새 MCP 설정을 반영하지 않으면 Codex 세션을 새로 시작한다.
