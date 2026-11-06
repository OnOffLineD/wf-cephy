# AGENTS.md — 다중 AI 협업 운영 규약 (Antigravity & Claude Code with orchestra-kit)

> 이 문서는 프로젝트 루트에 두고 오케스트레이터 에이전트(Antigravity)와 빌더 에이전트(Claude Code CLI)의 공통 운영 규칙 파일로 사용합니다.
> 실제 작업 격리와 검증 강제는 `orchestra.py` 디스패처가 수행하고, 프로젝트 고유 검증 설정은 `.orchestra/orchestra.toml`에서 관리합니다.

---

## 0. 다중 AI 협업 대원칙

1. **빌더 ≠ 검수자.** 코드를 쓴 주체(Claude Code)는 그 코드를 최종 승인하지 않는다.
2. **부탁하지 말고 기계적으로 강제한다.** 범위·보호 경로·검증·줄 수 한도는 프롬프트 권고가 아니라 `orchestra.py` 디스패처가 기계적으로 검사하고 차단한다.
3. **Worktree 격리가 기본.** 빌더는 저장소 밖 `../{repo}-worktrees/<ID>`에서만 수정 작업을 진행한다. 메인 체크아웃은 승인 후 `merge` 전까지 안전하게 보존된다.
4. **검증 기준은 빌드 전에 수립한다.** 빌더가 임의로 시험지를 만들거나 합격 기준을 낮추지 못하도록 오케스트레이터가 작업 패킷에 `acceptance`를 사전 정의한다.
5. **쓰기 주체는 한 번에 하나.** 디스패처의 파일 시스템 락(`lock`)이 동시성 충돌을 방지한다.
6. **역할을 합치지 않는다.** 한 CLI의 쿼터가 소진되면 다른 CLI가 작성과 검수를 겸하지 않고 즉시 작업을 중단(`ESCALATED`)하고 보고한다.

---

## 1. 3대 역할 분담 매트릭스

| 역할 | 담당 주체 | 주요 임무 | 금지 행동 |
| :--- | :--- | :--- | :--- |
| **오케스트레이터 (총괄 / CEO)** | **Antigravity** | 요구사항 분해, Tier 판정, Graphify 기반 외과수술적 컨텍스트 패킷 작성, 디스패처 실행, 진행률 관리 | 빌드 대상 코드 직접 작성 (Tier 1 초경량 패치 제외) |
| **빌더 (Builder)** | **Claude Code CLI** (`claude -p`) | 패킷 범위 안에서 최소 수정, 단위 테스트 추가, 1차 컴파일 및 자체 테스트 검증 | 임의 커밋, 기존 테스트 무력화, 허용 범위 밖 수정 |
| **1차 기계 검수 (Gates)** | **`orchestra.py`** | 허용/보호 범위 검사, 빌드·테스트 게이트 재실행, diff 상한선 검사, 실패 시 세션 피드백 및 재시도 | 주관적 판단, 아키텍처 재설계 강요 |
| **최종 검수 (Inspector)** | **Antigravity** | `.orchestra/runs/<ID>/REVIEW.md` 판독, diff 및 게이트 결과 기반 `verdict PASS/FAIL` 판정 | 스타일 트집, 무관한 다른 설계 강요 |
| **최종 머지** | **사용자 / Antigravity** | 승인된 브랜치(`orch/<ID>`) 확인 후 `orchestra.py merge <ID>` 실행 | 미승인 브랜치 강제 머지 |

---

## 2. Tier 판정 (오케스트레이터의 작업 분기)

| Tier | 판정 기준 | 처리 절차 |
| :--- | :--- | :--- |
| **Tier 1 (Fast-Track)** | 1개 파일, 20줄 이내(설정값/단일 가드), 보호 경로·위험 패턴 무관 | 오케스트레이터 직접 수정 → `python orchestra.py check` → 통과 시 직접 커밋 |
| **Tier 2 (Orchestra Dispatch)** | 2개 이상 파일, 20줄 초과, 로직/알고리즘 변경, 또는 `check`가 `ESCALATE` 반환 | 작업 패킷 작성(`.orchestra/tasks/<ID>.toml`) → `python orchestra.py run <ID>` |

> **주의**: Tier 1은 **사후 측정**으로 확정합니다. `check`가 `ESCALATE`를 반환하면 즉시 수정을 롤백하고 Tier 2 패킷으로 전환합니다.

---

## 3. 표준 협업 흐름 (Propose → Build → Probe → Compose)

```
[1. Propose]  Antigravity: python orchestra.py new T-001 --title "작업명"
              Graphify로 의존성 심볼 추출 후 .orchestra/tasks/T-001.toml 작성
[2. Build]    Antigravity: python orchestra.py run T-001
              -> Worktree 생성 -> Claude Code 실행 -> 범위 검사 -> 게이트 실행(probe.py)
              -> 실패 시 세션 유지(--resume) 최대 3회 자동 복원
[3. Probe]    READY_FOR_REVIEW 상태 도달 시:
              Antigravity가 .orchestra/runs/T-001/REVIEW.md 검수 후 판정:
              -> python orchestra.py verdict T-001 PASS (또는 FAIL --notes "...")
              -> FAIL 시: python orchestra.py revise T-001
[4. Compose]  APPROVED 상태 도달 시:
              사용자 또는 Antigravity가 python orchestra.py merge T-001 실행
              배운 점은 EXPERIENCE.md에 자동/수동 누적 기록
```

### 상태별 분기 표 (`ORCHESTRA_STATUS=`)

| 반환 상태 | 의미 | 오케스트레이터(Antigravity) 조치 |
| :--- | :--- | :--- |
| `READY_FOR_REVIEW` | 범위·게이트 통과, 검수 대기 | `REVIEW.md` 확인 후 `verdict <ID> PASS\|FAIL` |
| `APPROVED` | 최종 검수 통과 | 사용자에게 변경 요약 보고 후 `merge <ID>` |
| `REJECTED` | 검수 반려 | 반려 사유 확인 후 `revise <ID>` 실행 |
| `ESCALATED` | 시도/반려 한도 초과 | **즉시 중단 후 사용자에게 보고.** 패킷 분할 또는 수동 개입 논의 |
| `BLOCKED` | 빌더가 명세 모순 보고 | 패킷의 모순 수정 후 `clean <ID>` -> `run <ID>` |
| `BUILDER_ERROR` | CLI 오류/쿼터 소진 | 로그 확인. 쿼터 문제 시 역할을 무리하게 합치지 않고 대기 |
| `MERGED` | 메인 체크아웃 반영 완료 | 상태 정리 완료, 후속 작업 진행 |

---

## 4. Graphify-First 맥락 절약 및 작업 패킷 규칙

### 4.1 외과수술적 컨텍스트 스코핑 (Graphify-First Gate)
- 빌더에게 프로젝트 전체 소스나 방대한 디렉터리를 덤프하지 않습니다.
- 오케스트레이터는 작업 착수 전 반드시 `graphify query "<Symbol>"` 또는 `graphify path`를 통해 수정 대상 심볼과 의존성 경로를 확인하고, **포인터(파일:심볼 + 핵심 명세)** 형태로만 패킷에 제공합니다.

### 4.2 작업 패킷 명세 (`.orchestra/tasks/<ID>.toml`)
```toml
id    = "T-001"
title = "버스트 DPS 계산 시 크리티컬 티어 가중치 반영"
tier  = 2

goal = """
calculate_burst_dps()가 크리티컬 확률이 100%를 초과할 때(티어 2 이상) 
각 티어별 데미지 배수를 가중 평균하여 정확한 기대 DPS를 산출한다.
"""

[scope]
allow = [
  "scripts/warframe_damage_engine.py",
  "tests/test_warframe_damage_engine.py"
]
forbid = []
max_files = 2
max_diff_lines = 120

[context]
hints = [
  "scripts/damage_formulas.py: average_crit_mult() - 크리티컬 배수 단일 진실 공급원",
  "scripts/warframe_damage_engine.py: calculate_burst_dps() - 대상 메서드"
]

[acceptance]
cases = [
  "crit_chance=1.5, crit_mult=2.0 -> average_crit_mult == 2.5",
  "crit_chance=2.2, crit_mult=3.0 -> average_crit_mult == 5.4"
]
commands = ["python -m pytest tests/test_warframe_damage_engine.py -k test_crit"]

[limits]
max_attempts = 3
```

---

## 5. 최종 검수 기준표 (Fail-Closed)

최종 검수 판정 시 FAIL 사유는 아래 **4대 항목**으로 한정하며, 반드시 **[파일:줄]**을 지목해야 합니다:
1. **기능 결함**: 목표(`goal`)나 `acceptance` 케이스를 만족하지 못하는 버그 또는 로직 오류.
2. **범위/명세 위반**: 요청하지 않은 부가 기능 추가, 비인가 동작 변경, 숨은 사이드이펙트.
3. **안정성 결여**: 예외 처리 누락으로 인한 크래시, 무한 루프, 메모리 누수, 상태 손상 위험.
4. **허위/무력화 테스트**: 단언문(assert)이 없거나 무의미한 참(True) 비교, 테스트를 통과시키기 위한 조건 왜곡.

> **주의**: 개인적인 스타일, 변수명 취향, 사소한 포맷팅은 FAIL 사유가 될 수 없으며, `notes`에 조언으로만 남깁니다. 검수 응답이 깨지거나 불명확할 경우 안전을 위해 **무조건 FAIL로 간주(Fail-Closed)**합니다.

---

## 6. WF-Companion 도메인 및 제품 가이드라인

1. **NO FORCED MODDING GENERATION**: 8모드 자동 완성 빌드 생성을 강제하지 않습니다. 사용자 질의응답 및 스크린샷 진단 지원을 최우선합니다.
2. **SCREENSHOT MOD DIAGNOSTIC**:
   - 인게임 모딩/리벤 화면 캡처 입력 시 OCR을 통해 무기명 및 모드/스탯을 파싱합니다.
   - 수학 엔진을 가동하여 **기대 DPS, 버스트 DPS, 최대 크리티컬(Peak), 최저 크리티컬(Trough)**을 브리핑합니다.
   - 정보가 불충분할 경우 명확한 재캡처 가이드를 친절하게 제시합니다.
3. **3-TIER STRICT CHAT ROUTING**:
   - **Level 1 (스몰톡)**: 인사, 피로 호소, 일상 대화 -> 위트 있는 세팔론 오디스(Cephalon Ordis) 페르소나 응답. 빌드 템플릿 강제 출력 금지.
   - **Level 2 (게임 가이드/공략)**: 보스 패턴, 속성 상성, 퀘스트 -> RAG 검색 기반 100% 실전 가이드 제공.
   - **Level 3 (스크린샷 진단)**: 이미지 기반 OCR 진단 및 데미지 엔진 평가.
4. **UI/UX STANDARDS**:
   - 카카오톡 스타일 1:1 채팅 UI 및 워프레임 다크 테마 유지.
   - 실시간 월드 이벤트(시터스 낮/밤, 두비리, 출격) 상시 체크리스트 제공.
   - 모든 JSON 및 텍스트 파일 입출력 시 UTF-8 인코딩 강제.

---

## 7. 주요 CLI 명령 요약

```bash
# 1. 새 작업 패킷 생성
python orchestra.py new <ID> --title "<작업명>"

# 2. 빌더 디스패치 및 게이트 실행 (자동 모드)
python orchestra.py run <ID>

# 3. 수동 점검 모드 (빌더 프롬프트를 확인하고 진행할 때)
python orchestra.py run <ID> --hitl

# 4. 검수 판정 (오케스트레이터)
python orchestra.py verdict <ID> PASS
python orchestra.py verdict <ID> FAIL --notes "<파일:줄 사유>"

# 5. 반려 후 재작업 지시
python orchestra.py revise <ID>

# 6. 최종 브랜치 머지
python orchestra.py merge <ID>

# 7. Tier 1 초경량 패치 사후 점검
python orchestra.py check

# 8. 작업 상태 조회 및 정리
python orchestra.py status [<ID>]
python orchestra.py clean <ID> | --all
```
