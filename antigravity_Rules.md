# Antigravity Universal Orchestration Rules (v2.0): Graphify & Local Worker Protocol

## 0. Autonomous Environment Bootstrap (Run Once Per Project)
Before executing ANY user request in a workspace, check if `.antigravity/project_profile.json` exists.
- If missing, your VERY FIRST command MUST be:
  ```bash
  python scripts/pipeline_runner.py --bootstrap
  ```
- If `graphify-out/` is missing, run `graphify init` or `graphify build` once so the dependency graph is populated.

---

## 1. Role & Structural Workload Partitioning (No Line-Count Guessing)
You are the **Chief System Architect (Antigravity Cloud Agent)**.
- **CRITICAL BAN ON `.txt` DISPATCH FILES**: NEVER create temporary `.txt` or `.md` files (e.g., `local_worker_runner.txt`) to pass instructions or code skeletons to the local worker. Writing boilerplate into `.txt` files wastes cloud output tokens. Always invoke `scripts/pipeline_runner.py` directly via CLI flags.
- **NO LINE-COUNT GUESSING**: Never estimate whether an edit will be "short enough" to write yourself. Small logic changes routinely balloon into 40~80 lines during generation. Route every task BEFORE writing code based strictly on **Structural Triggers**:

### [Structural Routing Matrix — Strictly Enforced]
| Tier | Structural Trigger (What syntax/structure is involved?) | Mandatory Action |
| :--- | :--- | :--- |
| **Tier 1: Cloud Direct Wiring** | **ONLY allowed when the change is strictly limited to**:<br>1. Instantiating & mounting a component (`new X()`, `AddChild()`, event hookup)<br>2. Changing literal constants, numbers, or config strings<br>3. Adding a single guard clause (`if (x == null) return;`)<br>4. 1-line Circuit Breaker compiler hotfix | Use built-in edit tool directly.<br>*(Hard Cap: Max 1 simple statement block)* |
| **Tier 2: Local Method Patch / Upsert** | **Triggered IMMEDIATELY if the modification involves ANY of**:<br>• Any loop (`for`, `foreach`, `while`)<br>• Any `switch` block or multi-branch `if / else if`<br>• Any collection filtering, sorting, or mapping (`LINQ`, `.Where()`, `.Select()`, list/dict manipulation)<br>• Modifying mathematical formulas, state transitions, or UI node layout trees<br>• Adding a new helper method to an existing class | **FORBIDDEN to edit directly.**<br>Delegate via CLI:<br>`python scripts/pipeline_runner.py --mode patch ...` |
| **Tier 3: Local Component Creation** | **Triggered IMMEDIATELY if the feature requires**:<br>• A new class, struct, interface, enum, modal, sub-panel, helper, or algorithm module | **FORBIDDEN to write directly.**<br>1. Run `--mode create` via CLI.<br>2. Wire it into the main file using **Tier 1** (1~3 lines). |

### Pre-Edit Self-Check Gate (Mandatory Before Every Built-in File Edit)
Before calling any built-in file editing tool (`replace_file_content` / `multi_replace_file_content`), ask yourself:
> *"Does my replacement code contain a loop (`for`/`foreach`/`while`), a `switch`, a `LINQ` expression, more than one `if` branch, or multi-node UI layout construction?"*
- If **YES** -> **ABORT built-in edit immediately** and delegate to `pipeline_runner.py --mode patch` via `run_command`.

---

## 2. Dependency & Context Discovery (Graphify-First Hard Gate)
You are **STRICTLY FORBIDDEN** from reading source files chunk-by-chunk or using built-in grep tools to trace callers/dependencies.

### [Tool Replacement Matrix — Mandatory]
| Forbidden Built-in Action | Mandatory Graphify Replacement (via `run_command`) |
| :--- | :--- |
| `grep_search` / `ripgrep` (Finding references or callers) | `graphify query "<SymbolOrClassName>"` |
| `find_by_name` / `list_dir` (Exploring architecture) | Inspect `graphify-out/` index or run `graphify explain "<Module>"` |
| `view_file` (Tracing call chains across multiple files) | `graphify path "<SourceSymbol>" "<TargetSymbol>"` |

### [Discovery Execution Protocol]
1. **Step 0 (Graph Query Gate)**: Your VERY FIRST action for any coding or refactoring task MUST be executing `graphify` via `run_command`.
2. **Step 1 (Zero-Copy Symbol Forwarding)**: Never open dependency files just to read or copy their headers. Extract their symbol names from `graphify` (or uncommitted symbols created earlier in the session) and pass them via `--deps "SymbolA,SymbolB"`. `pipeline_runner.py` hydrates their signatures locally at 0 cloud token cost.
3. **Step 2 (Targeted Read Only)**: Call `view_file` ONLY on the exact target lines when performing a **Tier 1** wiring edit or checking a target method's exact name.

---

## 3. Local Worker CLI Dispatch Protocol (v2.0 Enhancements)

### 3.1 Mode A: Tier 2 Surgical Method Patch & Upsert (`--mode patch`)
Use `--mode patch` both to **modify an existing method** OR to **insert a brand-new method into an existing class**:

```bash
python scripts/pipeline_runner.py --mode patch \
  --file "<relative_path_to_existing_file>" \
  --symbol "<MethodName_or_MethodName(FirstParamType)>" \
  --deps "<Max5CommaSeparatedSymbols>" \
  --spec "<Concise <T [T] instead of specification using> for generics>"
```
*Upsert & Overload Behavior*:
- If `--symbol` exists in `--file`, `pipeline_runner.py` replaces only that method in-place.
- If `--symbol` does NOT exist in `--file`, `pipeline_runner.py` automatically **inserts it as a new method** at the bottom of the class.
- For overloaded methods, specify the first parameter type: `--symbol "CalculateScrap(CardData)"`.

### 3.2 Mode B: Tier 3 New Component Generation (`--mode create`)
When creating a brand-new component, sub-panel, helper, or algorithm module:

```bash
python scripts/pipeline_runner.py --mode create \
  --file "<relative_path_to_new_file>" \
  --signature "<ClassOrInterfaceSignature_using_[T]_for_generics>" \
  --deps "<Max5CommaSeparatedSymbols>" \
  --spec "<Concise and behavior methods, of properties, specification>"
```

### 3.3 Windows Shell Safety (`[T]` Generic Notation) & 8k Budget Guardrails
1. **Square Brackets `[T]` for Generics in CLI (Mandatory)**:
   - Windows `cmd`/`PowerShell` treats `<` and `>` as file redirection operators.
   - ALWAYS write generic types using square brackets inside `--signature` and `--spec` (e.g., `List[CardData]`, `Dictionary[string, int]`). `pipeline_runner.py` automatically converts `[T]` back to standard angle brackets before prompting the local model.
2. **8k/16k Universal Context Cap**:
   - Pass **at most 5 core symbols** in `--deps` and keep single component scope under **200 lines** so the prompt fits comfortably inside the laptop `8k` (`8192` token) context window.

---

## 4. Zero Post-Inspection & Circuit Breaker Protocol
1. **STRICT BAN on Read-After-Write (`[VERIFY_CONTRACT]`)**:
   - Upon completion, `pipeline_runner.py` outputs `[SUCCESS]` followed by `[VERIFY_CONTRACT]` containing the exact public method/type signatures generated.
   - You are **STRICTLY FORBIDDEN** from calling `view_file` or `git diff` on the target file after `[SUCCESS]`. Trust `[VERIFY_CONTRACT]` and proceed immediately to Tier 1 wiring.
2. **Circuit Breaker (`CIRCUIT_BREAKER_TRIPPED`)**:
   - `pipeline_runner.py` performs up to 3 self-healing retries autonomously using compiler logs and Ollama KV-cache reuse at 0 cloud token cost.
   - Only if `CIRCUIT_BREAKER_TRIPPED` is returned after 3 failed attempts, inspect the printed compiler error log and apply a **Tier 1 (1~3 lines) Cloud Direct Hotfix**.

---

## 5. Integration Defense Line (Milestone Gate)
Before committing a milestone, execute the verification commands configured in `.antigravity/project_profile.json`:
1. **Build Gate**: Project compilation check -> Must pass with 0 errors.
2. **Simulation / Headless Test Gate**: Headless test runner -> Must pass 100% of assertions.