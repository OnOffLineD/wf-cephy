# orchestra-kit

구독형 AI 코딩 CLI 두세 개를 **오케스트레이터 / 빌더 / 검수자**로 나눠 쓰는 범용 키트입니다.
어떤 언어·프로젝트든 git 저장소면 쓸 수 있고, 프로젝트별 차이는 설정 파일 하나에만 둡니다.

| 파일 | 역할 |
|---|---|
| `orchestra.py` | 디스패처. 단일 파일, Python 3.11+ 표준 라이브러리만 사용 |
| `AGENTS.md` | 운영 규약. 오케스트레이터 에이전트의 규칙 파일로 사용 |
| `examples/` | 언어별 설정 조각과 작업 패킷 예시 |

## 디스패처가 강제하는 것

- **worktree 격리**: 빌더는 저장소 밖 `../<repo>-worktrees/<ID>`에서만 작업합니다. 메인 체크아웃은 `merge` 전까지 그대로입니다.
- **기계적 범위 검사**: 허용 경로 밖이나 보호 경로를 건드리면 그 파일을 되돌리고 시도를 실패 처리합니다. 파일 수와 diff 줄 수 상한도 검사합니다.
- **게이트 재실행**: 빌드·테스트는 빌더의 보고가 아니라 디스패처가 직접 돌립니다. 게이트가 만든 산출물은 diff에서 자동 제외합니다.
- **재시도와 서킷 브레이커**: 실패 내용을 같은 세션에 이어 보내고(`--resume`), 시도 3회·반려 2회를 넘기면 `ESCALATED`로 멈춥니다.
- **fail-closed 검수**: 자동 검수자가 형식에 맞는 판정을 내지 않으면 FAIL입니다.
- **단일 쓰기 락**, **프로세스 트리 타임아웃**, **API 키 제거**(구독 세션 사용 강제).

## 설치

1. Python 3.11 이상, Git, 사용할 CLI(`claude`, `agy`, `codex` 등) 로그인
2. `orchestra.py`를 원하는 곳에 둡니다. 예: `C:\tools\orchestra.py` (여러 프로젝트 공용) 또는 저장소의 `scripts/`
3. 대상 저장소에서:

```powershell
cd D:\work\my_project
python C:\tools\orchestra.py init
```

`init`은 다음을 만듭니다.

```
.orchestra/
  orchestra.toml        # 프로젝트별 설정 (게이트, 빌더/검수자 명령, 보호 경로)
  tasks/TEMPLATE.toml   # 작업 패킷 템플릿
  prompts/              # builder.md / revise.md / review.md (수정 가능)
  EXPERIENCE.md         # 교훈 기록
  runs/                 # 실행 기록 (.gitignore 처리됨)
```

4. `AGENTS.md`를 저장소 루트에 복사합니다.
5. **`.orchestra/`와 `AGENTS.md`를 커밋합니다.** worktree는 마지막 커밋에서 만들어지므로, 커밋하지 않은 변경은 빌더에게 보이지 않습니다.

## 설정에서 꼭 바꿀 세 곳 (`.orchestra/orchestra.toml`)

**1. 게이트** — 프로젝트의 빌드·테스트 명령

```toml
[verify]
gates = ["dotnet build -c Debug", "dotnet test --no-build"]
```

언어별 예시는 `examples/gates.md`에 있습니다.

**2. 빌더 허용 도구** — 빌더가 스스로 빌드·테스트를 돌려 볼 수 있게 해당 명령을 추가합니다.

```toml
"--allowedTools", "Read,Edit,Write,Glob,Grep,Bash(git status:*),Bash(git diff:*),Bash(dotnet build:*),Bash(dotnet test:*)"
```

**3. 보호 경로** — 빌더가 절대 수정하면 안 되는 곳(기존 테스트, 락 파일 등)

```toml
[scope]
protected = ["tests/**", "*.lock"]
```

빌드 산출물(bin/, obj/, node_modules/, __pycache__/ 등)은 `.gitignore`에 들어 있어야 합니다. 특히 `check` 명령은 메인 체크아웃에서 게이트를 돌리기 때문입니다.

## 사용

```powershell
python orchestra.py new T-001 --title "할인 시 세금 이중 계산 수정"
# .orchestra/tasks/T-001.toml 편집: goal, scope.allow, acceptance.cases/commands

python orchestra.py run T-001          # 빌더 실행 → 범위 → 게이트 → 검수 대기
# .orchestra/runs/T-001/REVIEW.md 를 검수자가 읽고:
python orchestra.py verdict T-001 PASS
python orchestra.py merge T-001        # 사람이 브랜치 확인 후
```

Tier 1(한 파일, 20줄 이내 수정)은 패킷 없이 직접 고친 뒤 검사만 합니다.

```powershell
python orchestra.py check              # OK면 직접 커밋, ESCALATE면 패킷으로 진행
```

모든 명령은 마지막 줄에 `ORCHESTRA_STATUS=<상태>`를 출력합니다. 오케스트레이터 에이전트는 이 줄로 분기합니다(상태표는 `AGENTS.md` 3절).

## 운영 모드

| 모드 | 방법 | 용도 |
|---|---|---|
| **HITL** | `run T-001 --hitl` | 디스패처가 프롬프트 파일과 worktree 경로를 알려주고, 사람이 빌더를 직접 돌린 뒤 Enter. 처음 1주일 패킷 형식 다듬기에 적합 |
| **자동** | `run T-001` | 오케스트레이터가 셸 명령으로 호출. 검수는 `manual`(오케스트레이터가 `verdict`) |
| **완전 자동** | `reviewer.mode = "command"` | 검수까지 CLI가 수행. 야간 배치용. `auto_merge`는 꺼두는 것을 권장 |
| **로컬 빌더** | `--profile local run T-001` | 빌더만 로컬 모델(Codex CLI + Ollama). 요청 시에만 사용 |

프로필은 `[profiles.<이름>]` 아래에 원하는 설정을 덮어써서 얼마든지 추가할 수 있습니다. `revise`는 처음 실행한 프로필을 기억합니다.

## 역할 배치 예시

```toml
# 기본: Antigravity = 오케스트레이터 + 최종검수(manual), Claude Code = 빌더
[builder]
cmd = ["claude", "-p", "--output-format", "json", "--permission-mode", "acceptEdits", ...]
[reviewer]
mode = "manual"

# 옵션 B: Antigravity = 빌더, Claude Code = 자동 검수
[builder]
cmd = ["agy", ...]          # agy의 비대화형 플래그는 `agy --help`로 확인
output = "text"
resume_args = []
[reviewer]
mode = "command"
cmd = ["claude", "-p"]
```

## 알려진 한계와 확인할 것

- **테스트 환경**: 가짜 빌더·검수자로 19개 시나리오(재시도, 범위 위반 복원, 산출물 제외, 반려와 재작업, 서킷 브레이커, fail-closed, 자동 머지, 락, HITL, 타임아웃, 프로필)를 Linux에서 검증했습니다. **Windows와 실제 CLI로는 아직 돌려보지 않았습니다.** 첫 실행은 HITL 모드나 작은 작업으로 확인하세요.
- **CLI 플래그**: `claude`, `codex`, `agy`의 플래그는 버전마다 바뀔 수 있습니다. 각 `--help`로 확인 후 `orchestra.toml`에 맞추세요.
- **Windows 명령 길이**: 프롬프트는 기본적으로 stdin으로 전달합니다. `{prompt}` 인자 방식은 `.cmd` 래퍼에서 약 8,000자 제한에 걸릴 수 있습니다.
- **세션 이어가기**는 `output = "claude-json"`일 때만 동작합니다. 다른 CLI는 매 시도마다 원래 명세와 실패 내용을 함께 보내므로 맥락이 끊겨도 진행됩니다.
- **경로 패턴**은 대소문자를 구분하며 `/` 구분자를 씁니다(Windows에서도 `src/**`).
- **엔진·GUI가 필요한 검증**(게임 엔진 런타임, 데스크톱 훅 등)은 게이트에 넣기 어렵습니다. 순수 로직을 분리해 단위 테스트로 검증하는 것이 무인 운영 품질을 가장 크게 좌우합니다.
