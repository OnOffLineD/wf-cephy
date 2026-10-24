# Multi-Agent Orchestration & RBAC Guidelines

본 프로젝트는 에이전트 간 역할 분리와 권한 격리를 통해 코드 무결성을 유지합니다.

## 1. Multi-Agent Roles (Strict RBAC)

| Agent ID | Primary Responsibility | Permission | Allowed Scope |
| :--- | :--- | :--- | :--- |
| **`AGENT_ARCH`** | 지식 그래프 인덱싱, 아키텍처/결합도 점검, 리팩토링 지시 | **READ-ONLY** | 전체 디렉토리 조회 및 `.graphify/` 분석 (수정 불가) |
| **`AGENT_CORE`** | DB 스키마, 핵심 비즈니스 로직, 엔진 및 파이프라인 | **READ / WRITE** | `core/`, `services/`, `engine/`, `main.py` 등 핵심 로직 |
| **`AGENT_UI`** | 디자인 시스템, 사용자 인터페이스, 프론트엔드 컴포넌트 | **READ / WRITE** | `ui/`, `frontend/`, `app.py`, `assets/` |
| **`AGENT_QA`** | 단위/통합/회귀 테스트 작성 및 실행, 정합성 검증 | **READ / WRITE (Tests)** | `tests/` 전용 쓰기, 그 외 소스 코드는 읽기 전용 |
| **`AGENT_SCRIBE`** | 진행 현황 기록, 변경 이력 추적, 원자적 Git 커밋 | **READ / WRITE (Docs/Git)** | `PROGRESS.md`, `CHANGELOG.md`, `.git/` 단독 제어 |

## 2. Inter-Agent Communication Protocol (`@[AGENT_PACKET]`)
에이전트 간 핸드오프 및 상태 보고는 아래 정형 블록만 사용하며, 블록 외부의 자유 텍스트는 배제합니다:

```yaml
@[AGENT_PACKET]
from: <AGENT_ID>
to: <AGENT_ID>
phase: <PHASE_ID>
status: <DISPATCHED | IN_PROGRESS | PASSED | FAILED | REFACTOR_REQUIRED>
graphify_nodes: [<queried_symbols>]
touched_files: [<modified_files>]
git_commit_ref: "<commit_hash_or_pending>"
payload:
  task: "<imperative_task_summary>"
  verification: "<probe_or_test_result>"
  issue: "<none_or_traceback>"
@[/AGENT_PACKET]
```

## 3. Atomic Commit Policy
- `AGENT_QA`의 Probe 검증 통과 즉시 Conventional Commits(`feat:`, `fix:`, `refactor:`, `test:`, `docs:`) 규칙으로 커밋을 생성합니다.
