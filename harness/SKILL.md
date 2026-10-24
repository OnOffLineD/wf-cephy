---
name: harness
description: "Scaffolds, manages, and executes Google Research Harness² recursive development environments for any project. Provides automated 8-component scaffolding, 3-gate probe verification, cross-project experience accumulation, and multi-agent RBAC enforcement."
---

# /harness

Any project can be elevated into a self-healing, self-improving autonomous engineering environment following **Google Research Harness²** and **IeumOps Master Directives**.

## Capabilities

1. **Autonomous Scaffolding (`/harness init`)**:
   - Detects project language/framework (Python, Node.js/TypeScript, Go, Rust).
   - Generates the 8-component harness architecture:
     - `.agents/guardrails/` (`engineering.md`, `domain_rules.md`)
     - `.agents/skills/` (`propose_probe_compose.md`)
     - `.agents/memory/` (`domain_context.md`)
     - `scripts/` (`probe.py` / `probe.mjs`, `record_experience.py` / `record_experience.mjs`)
     - `EXPERIENCE.md` (Linked to Global Experience Library)
     - `AGENTS.md` (Strict 5-agent RBAC & `@[AGENT_PACKET]` protocol)
     - `PROGRESS.md` (Real-time Phase Board)
2. **One-Stop Probe Runner (`/harness probe`)**:
   - Runs the 3-gate verification cycle:
     - Gate 1: Test Suite (`pytest`, `npm test`)
     - Gate 2: Domain Sanity & Rule Verification
     - Gate 3: Graphify AST / Knowledge Graph Integrity
   - Rejects unverified changes before commit (`Propose-Probe-Compose`).
3. **Experience Accumulation (`/harness record`)**:
   - Records post-mortem insights and debugging fixes into `EXPERIENCE.md`.
4. **Global Knowledge Sync (`/harness sync-global`)**:
   - Promotes reusable engineering patterns into the global library (`~/.gemini/config/skills/harness/GLOBAL_EXPERIENCE.md`).

---

## Instructions for Agents When Invoked

### 1. When `/harness init` or "하네스 초기화/설정" is requested:
1. **Git Initialization & Hygiene**:
   - Check if `.git` directory exists. If not, run `git init`.
   - Check if `.gitignore` exists. If not, copy the appropriate `.gitignore` template:
     - Python: `templates/python/.gitignore` $\rightarrow$ `.gitignore`
     - Node: `templates/node/.gitignore` $\rightarrow$ `.gitignore`
   - Install the Git pre-commit hook:
     - Copy `templates/hooks/pre-commit` to `.git/hooks/pre-commit`
     - On Windows/Unix, ensure executable permissions (`chmod +x .git/hooks/pre-commit` if supported).
     - *Effect*: Any future `git commit` will automatically run `scripts/probe.*` and abort if verification fails.
2. **Detect Project Tech Stack**:
   - Look for `pyproject.toml`, `requirements.txt`, `Pipfile` $\rightarrow$ **Python**
   - Look for `package.json`, `tsconfig.json` $\rightarrow$ **Node.js / TypeScript**
   - Otherwise fallback to generic/shell scripts.
3. **Deploy Templates**:
   - Copy templates from `C:/Users/2doo2/.gemini/config/skills/harness/templates/`:
     - `.agents/guardrails/engineering.md`
     - `.agents/guardrails/domain_rules.md`
     - `.agents/skills/propose_probe_compose.md`
     - `.agents/memory/domain_context.md`
     - `AGENTS.md`
     - `PROGRESS.md`
     - `EXPERIENCE.md`
   - Copy the language-specific probe and experience recorder:
     - Python: `templates/python/probe.py` & `templates/python/record_experience.py` $\rightarrow$ `scripts/`
     - Node: `templates/node/probe.mjs` & `templates/node/record_experience.mjs` $\rightarrow$ `scripts/`
4. **Run Immediate Probe Verification**:
   - Execute `python scripts/probe.py` (or node runner) to confirm baseline integrity.
5. **Initial Atomic Git Commit**:
   - Stage all generated files: `git add .agents/ scripts/ .gitignore AGENTS.md PROGRESS.md EXPERIENCE.md`
   - Commit initial scaffold: `git commit -m "chore(harness): initialize Google Research Harness² architecture"`
6. **Sync Graphify**:
   - If `graphify` is installed, run `graphify .` to initialize the project knowledge graph.

### 2. When `/harness probe` or "프로브 실행/검증" is requested:
1. Run the project's probe runner (`python scripts/probe.py`).
2. If any gate fails:
   - Output structured error traceback.
   - Enter internal debugging loop (Propose-Probe-Compose) without waiting for user intervention.
3. If all gates pass:
   - Output `@[AGENT_PACKET]` with `status: PASSED`.

### 3. When `/harness record` or "경험 기록" is requested:
1. Run `python scripts/record_experience.py "<Title>" "<Symptom>" "<Solution>" "<Lesson>"`.
2. Verify `EXPERIENCE.md` is updated.

---

## Mandatory Engineering Directives
- **Zero Conversational Filler**: Output structured IPC blocks (`@[AGENT_PACKET]`), CLI commands, and diffs only.
- **Graphify-First Mandate**: Do not dump entire files; query specific AST symbols or classes.
- **Surgical Changes**: Never refactor neighboring clean code or docstrings.
