# 언어·스택별 게이트 예시 (`[verify].gates`, `[project].setup`, 빌더 허용 도구)

게이트는 위에서부터 순서대로 실행되고 첫 실패에서 멈춥니다. 빠른 검사를 앞에 두세요.

| 스택 | setup | gates | 빌더 allowedTools에 추가 |
|---|---|---|---|
| .NET / C# | `dotnet restore` | `dotnet build -c Debug --no-restore`, `dotnet test --no-build` | `Bash(dotnet build:*)`, `Bash(dotnet test:*)` |
| Godot 4 C# | `dotnet restore` | `dotnet build`, `dotnet test --no-build` (엔진 비의존 로직 테스트 프로젝트) | 위와 동일 |
| Python | `pip install -e .[dev]` | `python -m ruff check .`, `python -m pytest -q` | `Bash(python -m pytest:*)` |
| Node / TS | `npm ci` | `npm run lint`, `npx tsc --noEmit`, `npm test -- --run` | `Bash(npm test:*)`, `Bash(npx tsc:*)` |
| Rust | | `cargo build`, `cargo test` | `Bash(cargo build:*)`, `Bash(cargo test:*)` |
| Go | | `go build ./...`, `go vet ./...`, `go test ./...` | `Bash(go test:*)` |
| Unity | | 에디터 배치 모드 테스트(`Unity -batchmode -runTests ...`)는 느리므로 순수 C# 라이브러리 분리 후 `dotnet test` 권장 | |

## 위험 패턴 예시 (`[tier1].risk_patterns`)

추가된 줄에 걸리면 Tier 1에서 무조건 ESCALATE합니다.

```toml
risk_patterns = [
  "DllImport|LibraryImport|extern\\s",   # 네이티브 호출
  "\\bunsafe\\b",
  "eval\\(|exec\\(",
  "subprocess|os\\.system|Process\\.Start",
  "DROP\\s+TABLE|DELETE\\s+FROM",
  "(?i)password|secret|api[_-]?key",
]
```
