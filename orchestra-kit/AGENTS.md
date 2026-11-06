# AGENTS.md — 다중 AI 개발 운영 규약 (범용)

> 이 문서는 프로젝트 루트에 두고 오케스트레이터 에이전트(예: Antigravity)의 규칙 파일로 사용합니다.
> 실제 강제는 `orchestra.py`가 하고, 이 문서는 "언제 무엇을 실행하는가"를 정합니다.
> 프로젝트 고유 사항(빌드 명령, 보호 경로, 위험 패턴)은 `.orchestra/orchestra.toml`에만 적습니다.

---

## 0. 대원칙

1. **빌더 ≠ 검수자.** 코드를 쓴 주체는 그 코드를 승인하지 않는다.
2. **부탁하지 말고 강제한다.** 범위·검증·한도는 프롬프트가 아니라 디스패처가 기계적으로 검사한다.
3. **격리가 기본.** 빌더는 git worktree에서만 쓴다. 메인 체크아웃은 사람이(또는 명시적 auto_merge가) 머지할 때만 바뀐다.
4. **검증 기준은 빌드 전에 쓴다.** 빌더가 자기 시험지를 만들지 않는다.
5. **쓰기 주체는 한 번에 하나.** 디스패처의 락이 보장한다.
6. **역할을 합치지 않는다.** 한 CLI의 쿼터가 바닥나면, 남은 CLI가 작성과 검수를 겸하게 하지 말고 멈춘다.

---

## 1. 역할

| 역할 | 기본 담당 | 하는 일 | 하지 않는 일 |
|---|---|---|---|
| **오케스트레이터 (CEO)** | Antigravity | 요구 분해, Tier 판정, 작업 패킷 작성(검증 기준 포함), 디스패처 실행, 진행 기록 | 빌드 대상 코드 직접 작성(Tier 1 제외) |
| **빌더** | Claude Code CLI (`claude -p`) | 패킷 범위 안에서 최소 수정, 새 테스트 추가, 스스로 빌드/테스트 시도 | 커밋, 기존 테스트 수정, 범위 밖 수정 |
| **1차 검수 (게이트)** | `orchestra.py` (기계) | 범위 검사, 빌드·테스트 게이트 재실행, 실패 시 피드백과 재시도 | 판단이 필요한 리뷰 |
| **최종 검수** | 오케스트레이터 또는 별도 CLI | diff만 읽고 고정 기준표로 PASS/FAIL | 스타일 트집, 다른 설계 강요 |
| **머지** | 사람 | 승인된 브랜치를 확인하고 `merge` | — |

다른 배치도 `orchestra.toml`만 바꾸면 된다.

- **옵션 B**: Antigravity가 빌더(`builder.cmd = ["agy", ...]`), Claude Code가 검수(`reviewer.mode = "command"`, `reviewer.cmd = ["claude", "-p"]`)
- **로컬 빌더 (요청 시만)**: `orchestra.py --profile local run <ID>` — 빌더=로컬 모델, 검수=클라우드. 세 주체가 모두 달라 독립성이 가장 높다.

---

## 2. Tier 판정 (오케스트레이터가 작업 시작 전에)

| Tier | 기준 | 처리 |
|---|---|---|
| **1** | 1개 파일, 20줄 이내(설정값), 보호 경로·위험 패턴 무관 | 오케스트레이터가 직접 수정 → `orchestra.py check` → OK면 직접 커밋 |
| **2** | 그 외 전부, 또는 `check`가 `ESCALATE` | 작업 패킷 작성 → `orchestra.py run` |

Tier 1은 **사후 측정**으로 확정한다. `check`가 `ESCALATE`를 내면 수정분을 되돌리고(또는 커밋하지 말고) Tier 2로 다시 진행한다.

---

## 3. 표준 흐름 (Propose → Build → Probe → Compose)

```
[Propose]  오케스트레이터: orchestra.py new T-012 --title "..."  → 패킷 작성
[Build]    orchestra.py run T-012
              worktree 생성 → 빌더 실행 → 범위 검사 → 게이트(빌드·테스트)
              실패 시 피드백과 함께 같은 세션 재시도 (최대 max_attempts)
[Probe]    READY_FOR_REVIEW → 검수자가 .orchestra/runs/T-012/REVIEW.md 판정
              orchestra.py verdict T-012 PASS            (또는 FAIL --notes "...")
              FAIL → orchestra.py revise T-012  (반려 2회면 ESCALATED)
[Compose]  APPROVED → 사람이 브랜치 확인 → orchestra.py merge T-012
              오케스트레이터: 배운 점이 있으면 EXPERIENCE.md에 추가
```

### 상태별 다음 행동 (오케스트레이터는 마지막 줄 `ORCHESTRA_STATUS=`만 보고 분기)

| 상태 | 의미 | 다음 행동 |
|---|---|---|
| `READY_FOR_REVIEW` | 범위·게이트 통과, 검수 대기 | REVIEW.md 판정 → `verdict` |
| `APPROVED` | 검수 통과 | 사용자에게 보고, 사용자가 `merge` |
| `REJECTED` | 검수 반려 | `revise` (반려 사유가 빌더에게 전달됨) |
| `ESCALATED` | 재시도 또는 반려 한도 초과 | **멈추고 사용자에게 보고.** 패킷을 쪼개거나 다시 쓸지 제안 |
| `BLOCKED` | 빌더가 명세 모순·불가 보고 | 패킷의 모순을 고친 뒤 `clean` → `run` |
| `BUILDER_ERROR` | CLI 실패(쿼터·인증·권한·타임아웃) | 로그 확인. 쿼터면 **역할을 합치지 말고** 대기 |
| `SETUP_FAILED` | worktree 준비 명령 실패 | 설정의 `setup` 확인 |
| `MERGED` | 반영 완료 | PROGRESS 확인, 종료 |

---

## 4. 작업 패킷 작성 규칙 (`.orchestra/tasks/<ID>.toml`)

- **goal**: 결과 하나. "무엇이 참이 되어야 하는가"로 쓴다. 방법은 강요하지 않는다.
- **scope.allow**: 빌더가 쓸 수 있는 파일. 좁을수록 좋다(보통 1~3개). 새 테스트 파일 위치도 포함한다.
- **scope.forbid**: 허용 범위 안이라도 건드리면 안 되는 곳.
- **context.hints**: 코드가 아니라 **포인터**(파일:심볼 + 한 줄 설명). 그래프 도구(graphify 등)나 grep 결과는 여기에 힌트로만 넣는다. **읽기는 넓게, 쓰기는 좁게.**
- **acceptance.cases**: 빌드 전에 쓰는 구체적 입력→기댓값. 빌더는 이것을 테스트로 옮긴다.
- **acceptance.commands**: 이 작업 전용 검증 명령. 전역 게이트 뒤에 디스패처가 직접 실행한다.
- 한 패킷 = 한 결과. 두 가지를 하게 되면 패킷을 나눈다.

---

## 5. 최종 검수 기준표 (모든 검수자 공통)

FAIL 사유는 아래 넷뿐이며, 각 항목은 **파일과 줄**을 지목해야 한다.

1. 목표나 acceptance case를 달성하지 못하는 버그·로직 오류
2. 범위·명세 위반(요청하지 않은 동작 변경, 숨은 부작용)
3. 크래시·행·리소스 누수·상태 손상으로 이어지는 예외 처리 누락
4. 동작을 실제로 검증하지 않는 테스트(항상 참, 모킹으로 무력화, 통과하도록 휜 테스트)

스타일·이름·포맷·취향은 notes에만 적고 FAIL 사유로 쓰지 않는다. 현재 설계가 틀리지 않았다면 다른 설계를 요구하지 않는다.
검수 응답이 없거나 형식이 깨지면 **FAIL로 간주한다(fail-closed).**

---

## 6. 서킷 브레이커와 한도

| 항목 | 기본값 | 초과 시 |
|---|---|---|
| 라운드당 빌더 시도 | 3회 (`limits.max_attempts`) | `ESCALATED` |
| 검수 반려 | 2회 (`limits.max_review_rounds`) | `ESCALATED` |
| 파일 수 / diff 줄 수 | 패킷 값, 없으면 설정 기본값 | 해당 시도 실패 |
| 빌더 프로세스 시간 | `builder.timeout_sec` | 프로세스 트리 종료, `BUILDER_ERROR` |

`ESCALATED`에서 자동으로 다시 시도하지 않는다. 사람이 결정한다.

---

## 7. 맥락 절약 규칙

- 빌더에게 코드를 붙여넣지 않는다. 패킷(포인터)만 준다. 빌더는 스스로 읽는다.
- 재시도는 같은 세션을 이어(`--resume`) 디버깅 맥락을 유지하고, **새 작업은 항상 새 세션**이다.
- 검수자는 diff(앞뒤 10줄 문맥)와 게이트 결과만 읽는다.
- 장기 기억은 대화가 아니라 파일에 남긴다: `PROGRESS.md`(디스패처가 자동 기록), `EXPERIENCE.md`(오케스트레이터가 교훈 추가).

---

## 8. 금지 사항

- 빌더의 "테스트 통과했습니다" 보고를 근거로 승인하지 않는다. 디스패처 게이트 결과만 근거다.
- 검증 명령을 저장소 안 스크립트로 옮기지 않는다(빌더가 약화시킬 수 있음). `orchestra.toml`에 둔다.
- `.orchestra/` 설정을 빌더 작업 중에 수정하지 않는다.
- 같은 파일을 위임 중인 작업과 동시에 직접 수정하지 않는다.
- 승인되지 않은 브랜치를 `merge --force` 하지 않는다(사용자 명시 요청 제외).

---

## 9. 오케스트레이터 명령 요약

```bash
python orchestra.py new <ID> --title "<제목>"      # 패킷 생성 후 편집
python orchestra.py run <ID>                      # 자동 모드
python orchestra.py run <ID> --hitl               # 사람이 빌더를 직접 돌리는 모드
python orchestra.py --profile local run <ID>      # 로컬 모델 빌더 (요청 시만)
python orchestra.py verdict <ID> PASS|FAIL --notes "<파일:줄 사유>"
python orchestra.py revise <ID>
python orchestra.py merge <ID>                    # 사람이 확인 후
python orchestra.py check                         # Tier 1 사후 검사
python orchestra.py status [<ID>]
python orchestra.py clean <ID> | --all
```

결과 파일: `.orchestra/runs/<ID>/RESULT.json`(요약), `REVIEW.md`(검수용), `diff.patch`, 시도별 프롬프트·로그.
