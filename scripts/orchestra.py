#!/usr/bin/env python3
"""
orchestra.py - project-agnostic BUILDER/REVIEWER dispatcher for AI coding CLIs.

One orchestrator (e.g. Antigravity, or you) writes a task packet; this script runs
the builder CLI (e.g. `claude -p`) in an isolated git worktree, enforces the write
scope mechanically, runs the verification gates itself, retries with feedback, and
hands a clean diff to an independent reviewer. Nothing touches your main checkout
until you (or auto_merge) merge an approved branch.

Requires: Python 3.11+, git. No third-party packages.

Commands
  init                         create .orchestra/ (config, prompts, task template)
  new <ID> [--title T]         create .orchestra/tasks/<ID>.toml from the template
  run <ID|task.toml> [--hitl]  worktree -> builder -> scope -> gates -> review
  revise <ID> [--notes ..]     re-run builder on a REJECTED task with review notes
  verdict <ID> PASS|FAIL       record a manual review verdict
  merge <ID>                   merge an APPROVED branch into the current branch
  check                        Tier-1 fast-track check of uncommitted changes in place
  status [ID]                  list runs / show one run
  clean <ID>|--all             remove worktree(s) and unmerged branch(es)

Every command prints a final line `ORCHESTRA_STATUS=<STATUS>` for agents to parse.
"""
from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import json
import locale
import os
import re
import shutil
import signal
import subprocess
import sys
from pathlib import Path

if sys.version_info < (3, 11):
    sys.exit("orchestra.py needs Python 3.11+ (uses tomllib).")
import tomllib  # noqa: E402

VERSION = "1.0.0"
ORCH = ".orchestra"
ALWAYS_PROTECTED = [".orchestra/**", ".git/**"]
IS_WIN = os.name == "nt"

# Statuses
NEW, BUILDING, READY, APPROVED, REJECTED, MERGED = (
    "NEW", "BUILDING", "READY_FOR_REVIEW", "APPROVED", "REJECTED", "MERGED")
ESCALATED, BLOCKED, BUILDER_ERROR, SETUP_FAILED = (
    "ESCALATED", "BLOCKED", "BUILDER_ERROR", "SETUP_FAILED")
OK_STATUSES = {READY, APPROVED, MERGED}

# --------------------------------------------------------------------------- #
# Default files written by `init` (single-file distribution)
# --------------------------------------------------------------------------- #
DEFAULT_CONFIG = r'''# orchestra.toml - read from the MAIN checkout only. The builder works in a
# worktree and cannot weaken these settings (.orchestra/** is always protected).

[project]
base_branch   = ""                       # "" = whatever HEAD is when you run
worktree_root = "../{repo}-worktrees"    # keep OUTSIDE the repo, otherwise build
                                          # tools (MSBuild, pytest, jest...) may pick
                                          # up the worktree's files as duplicates
branch_prefix = "orch/"
auto_merge    = false                    # true = merge right after APPROVED
strip_api_keys = true                    # remove *_API_KEY so CLIs use subscriptions

# Commands run once in a fresh worktree (dependency restore, codegen, caches...).
setup = [
  # "dotnet restore", "npm ci", "pip install -e .",
]

[builder]
# Prompt goes to stdin unless an argument contains {prompt}.
# Verify flags against `claude --help` for your installed version.
cmd = ["claude", "-p", "--output-format", "json",
       "--permission-mode", "acceptEdits", "--max-turns", "40",
       "--allowedTools", "Read,Edit,Write,Glob,Grep,Bash(git status:*),Bash(git diff:*)"]
#      ^ add your build/test commands, e.g. "Bash(dotnet build:*)" or "Bash(npm test:*)"
resume_args = ["--resume", "{session_id}"]   # [] to always start fresh
output = "claude-json"                     # "claude-json" (session resume) | "text"
timeout_sec = 1800

# Local-model builder: see [profiles.local] below (`--profile local`).

[verify]
# Gates run by the dispatcher itself, in the worktree, in order, stop at first failure.
# They live here (not in the repo) so the builder cannot weaken them.
gates = [
  # "dotnet build -c Debug",
  # "dotnet test --no-build",
  # "python -m pytest -q",
  # "npm run lint && npm test",
]
timeout_sec = 1200

[scope]
# Always forbidden for the builder in addition to the task's own `forbid`.
protected = [
  # "tests/**",            # existing tests: builder may not edit them
  # "*.lock", "package-lock.json",
]
default_max_files = 5
default_max_diff_lines = 300

[limits]
max_attempts = 3          # builder runs per round (1 + 2 self-fix retries)
max_review_rounds = 2     # reviewer rejections that trigger ESCALATED (2 = one revise allowed)

[reviewer]
# "manual"  : stop at READY_FOR_REVIEW, the orchestrator agent reads REVIEW.md and
#             calls `orchestra.py verdict <ID> PASS|FAIL --notes ...`
# "command" : run `cmd` with the review prompt on stdin, parse the JSON verdict
#             (missing/broken verdict = FAIL, fail-closed)
# "off"     : gates passing = APPROVED (not recommended)
mode = "manual"
cmd = []                  # e.g. ["claude", "-p"] when the builder is someone else
timeout_sec = 900

# Named overrides, used with `orchestra.py --profile <name> run ...`.
# Anything above can be overridden; tables are merged.
[profiles.local.builder]
# Local model through Codex CLI + Ollama (no subscription quota). Verify flags with
# `codex exec --help`. Long prompts: on Windows prefer a real .exe over a .cmd shim.
cmd = ["codex", "exec", "--oss", "--full-auto", "{prompt}"]
resume_args = []
output = "text"
timeout_sec = 3600

[profiles.local.limits]
max_attempts = 4

[tier1]
# `orchestra.py check`: in-place fast track for tiny edits. Exceeding any of these
# means ESCALATE -> write a task and use `run`.
max_files = 1
max_diff_lines = 20
risk_patterns = [
  # regexes on ADDED lines that always force escalation, e.g.
  # "DllImport|LibraryImport", "\\bunsafe\\b", "eval\\(", "subprocess", "DROP TABLE",
]
'''

DEFAULT_TASK = r'''# Task packet. Written by the orchestrator (CEO), never by the builder.
id    = "{id}"
title = "{title}"
tier  = 2

goal = """
One concrete outcome. What must be true when this is done.
"""

[scope]
allow = [
  # "src/billing/**",          # files the builder may write (glob, repo-relative, "/")
]
forbid = [
  # "src/billing/legacy/**",
]
max_files = 3
max_diff_lines = 200

[context]
# Pointers, not code. Graph/grep output goes here as hints; the builder may read anything.
hints = [
  # "src/billing/invoice.py: Invoice.total() computes tax twice when discount > 0",
]

[acceptance]
# Write these BEFORE building. Concrete input -> expected output.
cases = [
  # "Invoice(100, discount=10, tax=0.1).total() == 99.0",
]
# Task-specific commands, run after the global gates (by the dispatcher).
commands = [
  # "python -m pytest -q tests/test_invoice.py",
]

[limits]
# max_attempts = 3
'''

PROMPT_BUILDER = r'''You are the BUILDER in a supervised pipeline. The current directory is an
isolated git worktree of the project; your changes are reviewed before anyone merges them.

{{SPEC}}

## Rules
- Make the smallest change that satisfies the goal. Edit in place; do not rewrite whole files.
- Write only inside the allowed scope. Out-of-scope edits are reverted automatically and the
  attempt counts as failed.
- Never weaken, delete or edit existing tests or verification scripts to make them pass.
  You may add NEW tests inside the allowed scope.
- Do not commit, create branches, or change git configuration.
- The dispatcher runs the verification commands itself; your claims are not trusted. Run them
  yourself if you can, to save attempts.
- If the goal is impossible or the spec contradicts itself, change nothing and end your reply
  with a line starting with `BLOCKED:` and the reason.
- Finish with a short report: files changed, what you did, anything uncertain.
'''

PROMPT_REVISE = r'''Your previous attempt for task {{TASK_ID}} did not pass (attempt {{ATTEMPT}} of {{MAX_ATTEMPTS}}).
Fix only what the failure below requires. Goal and scope rules are unchanged.

## Failure
{{FEEDBACK}}

## Original task (for reference)
{{SPEC}}

Same rules as before: minimal in-place edits, allowed scope only, never weaken tests,
no commits, `BLOCKED:` if impossible, short report at the end.
'''

PROMPT_REVIEW = r'''You are the independent REVIEWER. You did not write this code.
Judge ONLY the diff below against the task. The verification gates already passed.

{{SPEC}}

## Gate results
{{GATES}}

## Rubric
FAIL only for these, each citing file and line:
1. Bug or logic that does not achieve the goal / acceptance cases.
2. Scope or spec violation (unrequested behaviour change, hidden side effects).
3. Missing error handling that can crash, hang, leak resources or corrupt state.
4. Tests that do not really test the behaviour (tautological, mocked-away, or bent to pass).
Style, naming, formatting, personal preference -> put in "notes", never FAIL.
Do not propose a different design unless the current one is wrong.

## Output
End your reply with exactly one JSON object:
{"verdict": "PASS" | "FAIL", "issues": [{"file": "", "line": 0, "reason": ""}], "notes": ""}

## Diff ({{DIFF_STATS}})
```diff
{{DIFF}}
```
'''

GITIGNORE_LINES = [f"{ORCH}/runs/"]


# --------------------------------------------------------------------------- #
# Small utilities
# --------------------------------------------------------------------------- #
def now() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def say(msg: str) -> None:
    print(f"[orchestra] {msg}", flush=True)


def finish(status: str, code: int | None = None, extra: str = "") -> None:
    if extra:
        print(extra)
    print(f"ORCHESTRA_STATUS={status}", flush=True)
    sys.exit(code if code is not None else (0 if status in OK_STATUSES | {"OK", "INIT"} else 1))


def die(msg: str) -> None:
    print(f"[orchestra] ERROR: {msg}", file=sys.stderr, flush=True)
    print("ORCHESTRA_STATUS=ERROR", flush=True)
    sys.exit(2)


def decode(b: bytes) -> str:
    if not b:
        return ""
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode(locale.getpreferredencoding(False) or "utf-8", errors="replace")


def tail(text: str, n: int = 80) -> str:
    lines = text.rstrip().splitlines()
    return "\n".join(lines[-n:])


def kill_tree(p: subprocess.Popen) -> None:
    try:
        if IS_WIN:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            os.killpg(p.pid, signal.SIGKILL)
    except Exception:
        try:
            p.kill()
        except Exception:
            pass


def run_proc(args, cwd: Path, stdin_text: str | None = None, timeout: int | None = None,
             env: dict | None = None, shell: bool = False):
    """Run a process (tree-killed on timeout). Returns (rc, output, timed_out)."""
    if not shell:
        args = list(args)
        exe = shutil.which(args[0])  # honours PATHEXT on Windows (claude.cmd etc.)
        if exe is None:
            return 127, f"command not found: {args[0]}", False
        args[0] = exe
    kw: dict = {}
    if IS_WIN:
        kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kw["start_new_session"] = True
    p = subprocess.Popen(args, cwd=str(cwd), shell=shell, env=env,
                         stdin=subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kw)
    data = stdin_text.encode("utf-8") if stdin_text is not None else None
    try:
        out, _ = p.communicate(input=data, timeout=timeout)
        return p.returncode, decode(out), False
    except subprocess.TimeoutExpired:
        kill_tree(p)
        try:
            out, _ = p.communicate(timeout=30)
        except Exception:
            out = b""
        return -9, decode(out) + f"\n[orchestra] TIMEOUT after {timeout}s - process tree killed", True


def git(args: list[str], cwd: Path, check: bool = True) -> str:
    r = subprocess.run(["git", *args], cwd=str(cwd), stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed:\n{decode(r.stderr)}")
    return decode(r.stdout)


def git_ok(args: list[str], cwd: Path) -> bool:
    return subprocess.run(["git", *args], cwd=str(cwd), stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL).returncode == 0


def match_any(path: str, patterns: list[str]) -> bool:
    for p in patterns:
        p = p.replace("\\", "/").removeprefix("./")
        if fnmatch.fnmatchcase(path, p):
            return True
        if p.endswith("/**") and (path == p[:-3] or path.startswith(p[:-2])):
            return True
        if p.startswith("**/") and fnmatch.fnmatchcase(path, p[3:]):
            return True
    return False


def extract_json(text: str, key: str) -> dict | None:
    """Last JSON object in text that contains `key`."""
    dec = json.JSONDecoder()
    found = None
    for m in re.finditer(r"\{", text):
        try:
            obj, _ = dec.raw_decode(text[m.start():])
        except ValueError:
            continue
        if isinstance(obj, dict) and key in obj:
            found = obj
    return found


def render(template: str, values: dict) -> str:
    out = template
    for k, v in values.items():
        out = out.replace("{{" + k + "}}", str(v))
    return out


def bullets(items: list, empty: str = "(none)") -> str:
    return "\n".join(f"- {i}" for i in items) if items else empty


def deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        out[k] = deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


# --------------------------------------------------------------------------- #
# Project / config / state
# --------------------------------------------------------------------------- #
class Project:
    def __init__(self, start: Path, profile: str = ""):
        self.profile = profile
        try:
            top = git(["rev-parse", "--show-toplevel"], start).strip()
        except RuntimeError:
            die(f"{start} is not inside a git repository")
        self.root = Path(top)
        # If invoked from inside a linked worktree, use the main checkout.
        common = Path(git(["rev-parse", "--path-format=absolute", "--git-common-dir"],
                          self.root).strip())
        if common.name == ".git" and common.parent != self.root:
            self.root = common.parent
        self.orch = self.root / ORCH
        self.runs = self.orch / "runs"
        self.tasks = self.orch / "tasks"
        self.prompts = self.orch / "prompts"
        self.cfg = self._load_config()

    def _load_config(self) -> dict:
        defaults = tomllib.loads(DEFAULT_CONFIG)
        path = self.orch / "orchestra.toml"
        if not path.exists():
            return defaults
        try:
            cfg = deep_merge(defaults, tomllib.loads(path.read_text("utf-8")))
        except tomllib.TOMLDecodeError as e:
            die(f"orchestra.toml: {e}")
        profiles = cfg.pop("profiles", {})
        if self.profile:
            if self.profile not in profiles:
                die(f"profile '{self.profile}' not found in orchestra.toml "
                    f"(have: {', '.join(profiles) or 'none'})")
            cfg = deep_merge(cfg, profiles[self.profile])
        return cfg

    def prompt(self, name: str, fallback: str) -> str:
        p = self.prompts / name
        return p.read_text("utf-8") if p.exists() else fallback

    def worktree_root(self) -> Path:
        raw = self.cfg["project"]["worktree_root"].replace("{repo}", self.root.name)
        p = Path(raw)
        return (p if p.is_absolute() else (self.root / p)).resolve()

    def env(self) -> dict:
        env = dict(os.environ)
        if self.cfg["project"].get("strip_api_keys", True):
            for k in list(env):
                if k.endswith("_API_KEY"):
                    env.pop(k)
        return env

    def run_dir(self, tid: str) -> Path:
        return self.runs / tid

    def load_state(self, tid: str) -> dict | None:
        p = self.run_dir(tid) / "state.json"
        return json.loads(p.read_text("utf-8")) if p.exists() else None

    def save_state(self, st: dict) -> None:
        d = self.run_dir(st["id"])
        d.mkdir(parents=True, exist_ok=True)
        st["updated"] = now()
        (d / "state.json").write_text(json.dumps(st, ensure_ascii=False, indent=2), "utf-8")
        result = {k: st.get(k) for k in (
            "id", "title", "status", "branch", "worktree", "attempts_total", "review_rounds",
            "changed_files", "diff_lines", "session_id", "last_feedback", "review", "updated")}
        result["run_dir"] = str(d)
        (d / "RESULT.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")

    def progress(self, line: str) -> None:
        self.orch.mkdir(exist_ok=True)
        with open(self.orch / "PROGRESS.md", "a", encoding="utf-8") as f:
            f.write(f"- {now()} {line}\n")


class Lock:
    def __init__(self, proj: Project, tid: str, force: bool = False):
        self.path = proj.runs / ".lock"
        self.tid, self.force = tid, force

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.force and self.path.exists():
            self.path.unlink()
        try:
            fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            info = self.path.read_text("utf-8", errors="replace")
            die(f"another builder run holds the lock ({info.strip()}). "
                f"One writer at a time. If it is stale, rerun with --force-unlock.")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps({"task": self.tid, "pid": os.getpid(), "since": now()}))
        return self

    def __exit__(self, *exc):
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


# --------------------------------------------------------------------------- #
# Task packet
# --------------------------------------------------------------------------- #
def load_task(proj: Project, ref: str) -> tuple[dict, Path]:
    p = Path(ref)
    if not p.suffix:
        p = proj.tasks / f"{ref}.toml"
    elif not p.is_absolute() and not p.exists():
        p = proj.root / ref
    if not p.exists():
        die(f"task file not found: {p}")
    try:
        t = tomllib.loads(p.read_text("utf-8"))
    except tomllib.TOMLDecodeError as e:
        die(f"{p.name}: {e}")
    for k in ("id", "goal"):
        if not str(t.get(k, "")).strip():
            die(f"{p.name}: '{k}' is required")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", t["id"]):
        die("task id may only contain letters, digits, . _ -")
    sc = proj.cfg["scope"]
    t.setdefault("title", t["id"])
    t.setdefault("scope", {})
    t["scope"].setdefault("allow", [])
    t["scope"].setdefault("forbid", [])
    t["scope"].setdefault("max_files", sc["default_max_files"])
    t["scope"].setdefault("max_diff_lines", sc["default_max_diff_lines"])
    t.setdefault("context", {}).setdefault("hints", [])
    t.setdefault("acceptance", {})
    t["acceptance"].setdefault("cases", [])
    t["acceptance"].setdefault("commands", [])
    t.setdefault("limits", {})
    if not t["scope"]["allow"]:
        say("WARNING: scope.allow is empty - every non-protected file is writable.")
    return t, p


def spec_text(t: dict, proj: Project) -> str:
    s = t["scope"]
    forbid = ALWAYS_PROTECTED + proj.cfg["scope"]["protected"] + s["forbid"]
    gates = proj.cfg["verify"]["gates"] + t["acceptance"]["commands"]
    return "\n".join([
        f"# Task {t['id']}: {t['title']}",
        "", "## Goal", t["goal"].strip(),
        "", "## Write scope (enforced mechanically)",
        f"Allowed: {', '.join(s['allow']) if s['allow'] else '(any file not forbidden)'}",
        f"Forbidden: {', '.join(forbid)}",
        f"Limits: at most {s['max_files']} files and {s['max_diff_lines']} changed lines.",
        "", "## Context hints (start here; you may read any file)", bullets(t["context"]["hints"]),
        "", "## Acceptance cases (must hold)", bullets(t["acceptance"]["cases"]),
        "", "## Verification the dispatcher will run", bullets(gates, "(none configured)"),
    ])


# --------------------------------------------------------------------------- #
# Change inspection
# --------------------------------------------------------------------------- #
def parse_numstat(text: str) -> list[dict]:
    out = []
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        a, d, path = parts
        binary = a == "-"
        out.append({"path": path, "added": 0 if binary else int(a),
                    "deleted": 0 if binary else int(d), "binary": binary})
    return out


def worktree_changes(wt: Path, base: str) -> list[dict]:
    git(["add", "-A"], wt)
    return parse_numstat(git(["diff", "--cached", "--no-renames", "--numstat", base], wt))


def added_lines_from_diff(diff: str) -> list[str]:
    return [l[1:] for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++")]


def evaluate_scope(changes: list[dict], t: dict, proj: Project) -> tuple[list[str], list[str]]:
    """Returns (violation messages, revertible paths)."""
    s = t["scope"]
    protected = ALWAYS_PROTECTED + proj.cfg["scope"]["protected"] + s["forbid"]
    msgs, revert = [], []
    for c in changes:
        if match_any(c["path"], protected):
            msgs.append(f"protected path modified: {c['path']}")
            revert.append(c["path"])
        elif s["allow"] and not match_any(c["path"], s["allow"]):
            msgs.append(f"outside allowed scope: {c['path']}")
            revert.append(c["path"])
    kept = [c for c in changes if c["path"] not in revert]
    lines = sum(c["added"] + c["deleted"] for c in kept)
    if len(kept) > s["max_files"]:
        msgs.append(f"too many files: {len(kept)} > {s['max_files']}")
    if lines > s["max_diff_lines"]:
        msgs.append(f"diff too large: {lines} lines > {s['max_diff_lines']}")
    return msgs, revert


def revert_paths(wt: Path, base: str, paths: list[str]) -> None:
    for p in paths:
        git(["reset", "-q", base, "--", p], wt, check=False)
        if git_ok(["cat-file", "-e", f"{base}:{p}"], wt):
            git(["checkout", base, "--", p], wt, check=False)
        else:
            f = wt / p
            if f.exists():
                f.unlink()


def undo_gate_side_effects(wt: Path) -> None:
    """Gates (builds, tests) leave artifacts. The builder's work is already staged by
    worktree_changes(), so drop anything gates added or changed on top of the index."""
    for u in git(["ls-files", "--others", "--exclude-standard", "-z"], wt).split("\0"):
        if u:
            f = wt / u
            if f.is_file() or f.is_symlink():
                f.unlink()
    changed = [p for p in git(["diff", "--name-only", "-z"], wt).split("\0") if p]
    if changed:
        git(["checkout", "--", *changed], wt, check=False)


def run_gates(cmds: list[str], cwd: Path, run_dir: Path, label: str, proj: Project,
              timeout: int) -> tuple[bool, list[dict]]:
    results = []
    for i, c in enumerate(cmds, 1):
        say(f"gate {i}/{len(cmds)}: {c}")
        rc, out, to = run_proc(c, cwd, timeout=timeout, env=proj.env(), shell=True)
        (run_dir / f"{label}_gate{i}.log").write_text(f"$ {c}\n{out}", "utf-8")
        results.append({"cmd": c, "rc": rc, "timed_out": to, "tail": tail(out, 60)})
        if rc != 0:
            return False, results
    return True, results


# --------------------------------------------------------------------------- #
# Builder / reviewer invocation
# --------------------------------------------------------------------------- #
def invoke_builder(proj: Project, st: dict, prompt: str, wt: Path, rd: Path, label: str,
                   hitl: bool) -> dict:
    (rd / f"{label}_prompt.md").write_text(prompt, "utf-8")
    if hitl:
        print("\n" + "=" * 70)
        print(f"HUMAN-IN-THE-LOOP: run the builder yourself in:\n  {wt}")
        print(f"Prompt file:\n  {rd / f'{label}_prompt.md'}")
        print("Paste the prompt into the builder, let it finish, then press Enter here.")
        print("(Type 'blocked: <reason>' instead to stop the task.)")
        print("=" * 70)
        try:
            ans = input("> ").strip()
        except EOFError:
            ans = ""
        if ans.lower().startswith("blocked"):
            return {"ok": True, "blocked": ans, "summary": ans}
        return {"ok": True, "blocked": None, "summary": "(human-run)"}

    b = proj.cfg["builder"]
    args = list(b["cmd"])
    if not args:
        die("builder.cmd is empty in orchestra.toml")
    sid = st.get("session_id")
    if sid and st.get("attempts_total", 0) > 0 and b.get("resume_args"):
        args += [a.replace("{session_id}", sid) for a in b["resume_args"]]
    if any("{prompt}" in a for a in args):
        args = [a.replace("{prompt}", prompt) for a in args]
        stdin = None
    else:
        stdin = prompt
    say(f"builder running ({label}) ...")
    rc, out, to = run_proc(args, wt, stdin_text=stdin, timeout=int(b["timeout_sec"]),
                           env=proj.env())
    (rd / f"{label}_builder.log").write_text(out, "utf-8")
    res = {"ok": rc == 0 and not to, "rc": rc, "timed_out": to, "summary": tail(out, 30),
           "blocked": None}
    text = out
    if b.get("output") == "claude-json":
        j = extract_json(out, "session_id") or extract_json(out, "result")
        if j:
            if j.get("session_id"):
                st["session_id"] = j["session_id"]
            text = str(j.get("result", ""))
            res["summary"] = tail(text, 30)
            if j.get("is_error"):
                res["ok"] = False
    m = re.search(r"^\s*BLOCKED:(.*)$", text, re.M)
    if m:
        res["blocked"] = m.group(1).strip() or "builder reported BLOCKED"
    return res


def build_round(proj: Project, st: dict, t: dict, wt: Path, first_prompt: str, hitl: bool) -> str:
    """Builder -> scope -> gates loop. Returns the resulting status."""
    rd = proj.run_dir(t["id"])
    base = st["base"]
    max_att = int(t["limits"].get("max_attempts", proj.cfg["limits"]["max_attempts"]))
    gates = proj.cfg["verify"]["gates"] + t["acceptance"]["commands"]
    spec = spec_text(t, proj)
    prompt = first_prompt
    for attempt in range(1, max_att + 1):
        label = f"r{st['review_rounds']}a{attempt}"
        st["status"] = BUILDING
        proj.save_state(st)
        res = invoke_builder(proj, st, prompt, wt, rd, label, hitl)
        st["attempts_total"] = st.get("attempts_total", 0) + 1
        changes = worktree_changes(wt, base)

        if res.get("blocked") and not changes:
            st["last_feedback"] = f"BLOCKED: {res['blocked']}"
            return BLOCKED
        if not res["ok"]:
            why = ("timed out (raise builder.timeout_sec or split the task)" if res.get("timed_out")
                   else f"exited rc={res.get('rc')} (likely quota, auth, permissions or a bad cmd)")
            st["last_feedback"] = f"builder process {why}. Not retrying.\n{res['summary']}"
            return BUILDER_ERROR

        feedback = ""
        if not changes:
            feedback = "No file changes were made."
        else:
            msgs, revert = evaluate_scope(changes, t, proj)
            if revert:
                revert_paths(wt, base, revert)
            if msgs:
                feedback = ("Scope check failed:\n" + bullets(msgs) +
                            ("\nThe out-of-scope/protected edits listed above were reverted."
                             if revert else ""))
            else:
                ok, results = run_gates(gates, wt, rd, label, proj,
                                        int(proj.cfg["verify"]["timeout_sec"]))
                undo_gate_side_effects(wt)
                st["gates"] = results
                if ok:
                    st["changed_files"] = [c["path"] for c in changes]
                    st["diff_lines"] = sum(c["added"] + c["deleted"] for c in changes)
                    st["last_feedback"] = ""
                    say(f"attempt {attempt}: scope OK, {len(results)} gate(s) passed")
                    return READY
                f = results[-1]
                feedback = (f"Verification failed: `{f['cmd']}` exited {f['rc']}"
                            f"{' (timeout)' if f['timed_out'] else ''}.\nLast output:\n"
                            f"```\n{f['tail']}\n```")
        st["last_feedback"] = feedback
        say(f"attempt {attempt} failed: {feedback.splitlines()[0]}")
        proj.save_state(st)
        prompt = render(proj.prompt("revise.md", PROMPT_REVISE), {
            "TASK_ID": t["id"], "ATTEMPT": attempt + 1, "MAX_ATTEMPTS": max_att,
            "FEEDBACK": feedback, "SPEC": spec})
    return ESCALATED


def commit_worktree(proj: Project, st: dict, t: dict, wt: Path) -> None:
    git(["add", "-A"], wt)
    if not git(["diff", "--cached", "--name-only"], wt).strip():
        return
    ident = []
    if not git(["config", "user.email"], wt, check=False).strip():
        ident = ["-c", "user.name=orchestra", "-c", "user.email=orchestra@localhost"]
    msg = (f"orch({t['id']}): {t['title']}\n\nround {st['review_rounds']}, "
           f"attempts {st['attempts_total']}")
    git([*ident, "commit", "-q", "-m", msg], wt)
    diff = git(["diff", "--no-renames", st["base"], "HEAD"], wt)
    (proj.run_dir(t["id"]) / "diff.patch").write_text(diff, "utf-8")


def review_text(proj: Project, st: dict, t: dict, wt: Path) -> str:
    diff = git(["diff", "--no-renames", "-U10", st["base"], "HEAD"], wt)
    gates = "\n".join(f"- `{g['cmd']}` -> rc {g['rc']}" for g in st.get("gates", [])) or "- (none)"
    stats = f"{len(st.get('changed_files', []))} files, {st.get('diff_lines', 0)} lines"
    return render(proj.prompt("review.md", PROMPT_REVIEW), {
        "SPEC": spec_text(t, proj), "GATES": gates, "DIFF": diff, "DIFF_STATS": stats})


def do_review(proj: Project, st: dict, t: dict, wt: Path) -> str:
    rcfg = proj.cfg["reviewer"]
    mode = rcfg.get("mode", "manual")
    rd = proj.run_dir(t["id"])
    text = review_text(proj, st, t, wt)
    (rd / "REVIEW.md").write_text(text, "utf-8")
    if mode == "off":
        st["review"] = {"verdict": "PASS", "by": "off", "notes": "reviewer disabled"}
        return APPROVED
    if mode == "manual":
        say(f"waiting for review: {rd / 'REVIEW.md'}")
        return READY
    if not rcfg.get("cmd"):
        die("reviewer.mode = 'command' but reviewer.cmd is empty")
    say("reviewer running ...")
    args = list(rcfg["cmd"])
    if any("{prompt}" in a for a in args):
        args, stdin = [a.replace("{prompt}", text) for a in args], None
    else:
        stdin = text
    rc, out, to = run_proc(args, wt, stdin_text=stdin, timeout=int(rcfg["timeout_sec"]),
                           env=proj.env())
    (rd / f"r{st['review_rounds']}_review.log").write_text(out, "utf-8")
    payload = out
    j0 = extract_json(out, "result")  # unwrap claude --output-format json
    if j0 and isinstance(j0.get("result"), str):
        payload = j0["result"]
    v = extract_json(payload, "verdict")
    if rc != 0 or to or not v or str(v.get("verdict")).upper() not in ("PASS", "FAIL"):
        st["review"] = {"verdict": "FAIL", "by": "command",
                        "notes": "fail-closed: reviewer gave no valid verdict", "raw": tail(out, 20)}
        return REJECTED
    verdict = str(v["verdict"]).upper()
    st["review"] = {"verdict": verdict, "by": "command", "issues": v.get("issues", []),
                    "notes": v.get("notes", "")}
    return APPROVED if verdict == "PASS" else REJECTED


def after_review(proj: Project, st: dict, t: dict) -> str:
    """Apply escalation / auto-merge after a verdict."""
    rejections = st["review_rounds"] + 1
    if st["status"] == REJECTED and rejections >= int(proj.cfg["limits"]["max_review_rounds"]):
        st["status"] = ESCALATED
        st["last_feedback"] = (f"rejected {rejections} time(s) - circuit breaker. "
                               f"A human must decide.")
    if st["status"] == APPROVED and proj.cfg["project"].get("auto_merge"):
        merge_branch(proj, st)
    return st["status"]


def review_notes(st: dict) -> str:
    r = st.get("review") or {}
    lines = [f"Reviewer verdict: {r.get('verdict', '?')}"]
    for i in r.get("issues", []) or []:
        lines.append(f"- {i.get('file', '?')}:{i.get('line', '?')} {i.get('reason', '')}")
    if r.get("notes"):
        lines.append(f"Notes: {r['notes']}")
    return "\n".join(lines)


def merge_branch(proj: Project, st: dict) -> None:
    say(f"merging {st['branch']} into current branch ...")
    r = subprocess.run(["git", "merge", "--no-ff", "-m",
                        f"merge {st['branch']}: {st.get('title', '')}", st["branch"]],
                       cwd=str(proj.root), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if r.returncode != 0:
        subprocess.run(["git", "merge", "--abort"], cwd=str(proj.root),
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        die(f"merge failed, aborted. Resolve manually:\n{decode(r.stdout)}")
    st["status"] = MERGED
    remove_worktree(proj, st, delete_branch=True)


def remove_worktree(proj: Project, st: dict, delete_branch: bool) -> None:
    wt = Path(st.get("worktree", ""))
    if wt and wt.exists():
        git(["worktree", "remove", "--force", str(wt)], proj.root, check=False)
    git(["worktree", "prune"], proj.root, check=False)
    if delete_branch and st.get("branch"):
        git(["branch", "-D", st["branch"]], proj.root, check=False)


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
def cmd_init(proj: Project, a) -> None:
    for d in (proj.orch, proj.tasks, proj.prompts, proj.runs):
        d.mkdir(parents=True, exist_ok=True)
    files = {proj.orch / "orchestra.toml": DEFAULT_CONFIG,
             proj.tasks / "TEMPLATE.toml": DEFAULT_TASK.replace("{id}", "T-000").replace(
                 "{title}", "template"),
             proj.prompts / "builder.md": PROMPT_BUILDER,
             proj.prompts / "revise.md": PROMPT_REVISE,
             proj.prompts / "review.md": PROMPT_REVIEW,
             proj.orch / "EXPERIENCE.md": "# EXPERIENCE\n\nLessons learned (append, newest last).\n"}
    for p, content in files.items():
        if p.exists() and not a.force:
            say(f"keep existing {p.relative_to(proj.root)}")
        else:
            p.write_text(content, "utf-8")
            say(f"wrote {p.relative_to(proj.root)}")
    gi = proj.root / ".gitignore"
    existing = gi.read_text("utf-8").splitlines() if gi.exists() else []
    add = [l for l in GITIGNORE_LINES if l not in existing]
    if add:
        with open(gi, "a", encoding="utf-8") as f:
            f.write(("\n" if existing and existing[-1] else "") + "\n".join(add) + "\n")
        say(f".gitignore += {', '.join(add)}")
    say("next: edit .orchestra/orchestra.toml (verify.gates, builder.cmd), then "
        "`orchestra.py new T-001`. Commit .orchestra/ so worktrees inherit it.")
    finish("INIT")


def cmd_new(proj: Project, a) -> None:
    proj.tasks.mkdir(parents=True, exist_ok=True)
    p = proj.tasks / f"{a.id}.toml"
    if p.exists():
        die(f"{p} already exists")
    tmpl = proj.tasks / "TEMPLATE.toml"
    src = tmpl.read_text("utf-8") if tmpl.exists() else DEFAULT_TASK
    src = re.sub(r'^id\s*=.*$', f'id    = "{a.id}"', src, count=1, flags=re.M)
    src = re.sub(r'^title\s*=.*$', f'title = "{a.title or a.id}"', src, count=1, flags=re.M)
    src = src.replace("{id}", a.id).replace("{title}", a.title or a.id)
    p.write_text(src, "utf-8")
    say(f"created {p}")
    finish("OK", 0, extra=f"TASK_FILE={p}")


def cmd_run(proj: Project, a) -> None:
    t, tpath = load_task(proj, a.task)
    st = proj.load_state(t["id"])
    if st and st["status"] not in (BUILDER_ERROR, SETUP_FAILED, BLOCKED, ESCALATED):
        die(f"task {t['id']} already has a run in status {st['status']}. "
            f"Use `revise`, `verdict`, `merge`, or `clean {t['id']}` first.")
    if st:  # restarting after an error: start clean
        remove_worktree(proj, st, delete_branch=True)

    with Lock(proj, t["id"], a.force_unlock):
        base_ref = proj.cfg["project"]["base_branch"] or "HEAD"
        base = git(["rev-parse", base_ref], proj.root).strip()
        if git(["status", "--porcelain", "--untracked-files=no"], proj.root).strip():
            say("NOTE: main checkout has uncommitted changes; the worktree starts from the "
                "last commit and will NOT see them.")
        branch = proj.cfg["project"]["branch_prefix"] + t["id"]
        wt = proj.worktree_root() / t["id"]
        if wt.exists():
            git(["worktree", "remove", "--force", str(wt)], proj.root, check=False)
        git(["branch", "-D", branch], proj.root, check=False)
        wt.parent.mkdir(parents=True, exist_ok=True)
        git(["worktree", "add", "-q", "-b", branch, str(wt), base], proj.root)
        rd = proj.run_dir(t["id"])
        if rd.exists():
            shutil.rmtree(rd)
        rd.mkdir(parents=True)
        shutil.copyfile(tpath, rd / "task.toml")
        st = {"id": t["id"], "title": t["title"], "status": NEW, "base": base,
              "branch": branch, "worktree": str(wt), "task_file": str(tpath),
              "attempts_total": 0, "review_rounds": 0, "session_id": None,
              "created": now(), "hitl": a.hitl, "profile": proj.profile}
        proj.save_state(st)
        say(f"worktree {wt} on {branch} from {base[:10]}")

        for i, c in enumerate(proj.cfg["project"].get("setup", []), 1):
            say(f"setup {i}: {c}")
            rc, out, _ = run_proc(c, wt, timeout=1800, env=proj.env(), shell=True)
            (rd / f"setup{i}.log").write_text(out, "utf-8")
            if rc != 0:
                st["status"], st["last_feedback"] = SETUP_FAILED, f"setup failed: {c}\n{tail(out, 30)}"
                proj.save_state(st)
                proj.progress(f"{t['id']} {SETUP_FAILED}")
                finish(SETUP_FAILED)

        prompt = render(proj.prompt("builder.md", PROMPT_BUILDER), {"SPEC": spec_text(t, proj)})
        _complete_round(proj, st, t, wt, prompt, a.hitl)


def _complete_round(proj: Project, st: dict, t: dict, wt: Path, prompt: str, hitl: bool) -> None:
    status = build_round(proj, st, t, wt, prompt, hitl)
    st["status"] = status
    if status == READY:
        commit_worktree(proj, st, t, wt)
        st["status"] = do_review(proj, st, t, wt)
        after_review(proj, st, t)
    proj.save_state(st)
    proj.progress(f"{t['id']} {st['status']} (attempts {st['attempts_total']}, "
                  f"review rounds {st['review_rounds']})")
    print_summary(proj, st)
    finish(st["status"])


def cmd_revise(proj: Project, a) -> None:
    st = proj.load_state(a.id) or die(f"no run for {a.id}")
    if st["status"] != REJECTED:
        die(f"{a.id} is {st['status']}; revise works on REJECTED runs only")
    if st.get("profile") and not proj.profile:  # keep the builder the run started with
        proj = Project(proj.root, st["profile"])
    t, _ = load_task(proj, st["task_file"])
    wt = Path(st["worktree"])
    if not wt.exists():
        die(f"worktree missing: {wt}. Clean and run again.")
    notes = a.notes or (Path(a.notes_file).read_text("utf-8") if a.notes_file else review_notes(st))
    st["review_rounds"] += 1
    st["review"] = None
    with Lock(proj, a.id, a.force_unlock):
        max_att = int(t["limits"].get("max_attempts", proj.cfg["limits"]["max_attempts"]))
        prompt = render(proj.prompt("revise.md", PROMPT_REVISE), {
            "TASK_ID": t["id"], "ATTEMPT": 1, "MAX_ATTEMPTS": max_att,
            "FEEDBACK": "The independent reviewer rejected the change:\n" + notes,
            "SPEC": spec_text(t, proj)})
        _complete_round(proj, st, t, wt, prompt, a.hitl or st.get("hitl", False))


def cmd_verdict(proj: Project, a) -> None:
    st = proj.load_state(a.id) or die(f"no run for {a.id}")
    if st["status"] != READY:
        die(f"{a.id} is {st['status']}; verdict needs READY_FOR_REVIEW")
    t, _ = load_task(proj, st["task_file"])
    notes = a.notes or (Path(a.notes_file).read_text("utf-8") if a.notes_file else "")
    v = a.verdict.upper()
    st["review"] = {"verdict": v, "by": "manual", "notes": notes, "issues": []}
    st["status"] = APPROVED if v == "PASS" else REJECTED
    after_review(proj, st, t)
    proj.save_state(st)
    proj.progress(f"{a.id} verdict {v} -> {st['status']}")
    print_summary(proj, st)
    finish(st["status"])


def cmd_merge(proj: Project, a) -> None:
    st = proj.load_state(a.id) or die(f"no run for {a.id}")
    if st["status"] != APPROVED and not a.force:
        die(f"{a.id} is {st['status']}; only APPROVED runs merge (use --force to override)")
    merge_branch(proj, st)
    proj.save_state(st)
    proj.progress(f"{a.id} MERGED")
    finish(MERGED)


def cmd_clean(proj: Project, a) -> None:
    ids = [d.name for d in proj.runs.iterdir() if d.is_dir()] if a.all and proj.runs.exists() \
        else [a.id] if a.id else die("give a task id or --all")
    for tid in ids:
        st = proj.load_state(tid)
        if not st:
            continue
        if st["status"] == MERGED and not Path(st.get("worktree", "")).exists():
            continue
        remove_worktree(proj, st, delete_branch=st["status"] != MERGED)
        if st["status"] != MERGED:
            st["status"] = "CLEANED"
        proj.save_state(st)
        say(f"cleaned {tid}")
    finish("OK", 0)


def cmd_status(proj: Project, a) -> None:
    if a.id:
        st = proj.load_state(a.id) or die(f"no run for {a.id}")
        print(json.dumps(st, ensure_ascii=False, indent=2))
        finish(st["status"], 0)
    rows = []
    if proj.runs.exists():
        for d in sorted(proj.runs.iterdir()):
            st = proj.load_state(d.name) if d.is_dir() else None
            if st:
                rows.append((st["id"], st["status"], st.get("attempts_total", 0),
                             st.get("review_rounds", 0), st.get("updated", "")))
    if not rows:
        say("no runs yet")
    for r in rows:
        print(f"{r[0]:<20} {r[1]:<18} attempts={r[2]:<3} reviews={r[3]:<2} {r[4]}")
    finish("OK", 0)


def cmd_check(proj: Project, a) -> None:
    """Tier-1 fast track: inspect uncommitted changes in the main checkout, read-only."""
    tc = proj.cfg["tier1"]
    root = proj.root
    excl = ["--", ".", f":(exclude){ORCH}"]
    changes = parse_numstat(git(["diff", "HEAD", "--no-renames", "--numstat", *excl], root))
    diff = git(["diff", "HEAD", "--no-renames", "-U0", *excl], root)
    added = added_lines_from_diff(diff)
    for u in git(["ls-files", "--others", "--exclude-standard", *excl], root).splitlines():
        try:
            content = (root / u).read_text("utf-8", errors="replace").splitlines()
        except (IsADirectoryError, OSError):
            content = []
        changes.append({"path": u, "added": len(content), "deleted": 0, "binary": False})
        added += content
    # The orchestrator's own bookkeeping (.orchestra/) is not part of the code change.
    changes = [c for c in changes if not c["path"].startswith(ORCH + "/")]
    reasons = []
    if not changes:
        say("no uncommitted changes")
        finish("OK", 0)
    protected = proj.cfg["scope"]["protected"]
    for c in changes:
        if match_any(c["path"], protected):
            reasons.append(f"protected path changed: {c['path']}")
    lines = sum(c["added"] + c["deleted"] for c in changes)
    if len(changes) > tc["max_files"]:
        reasons.append(f"{len(changes)} files > tier1 max {tc['max_files']}")
    if lines > tc["max_diff_lines"]:
        reasons.append(f"{lines} changed lines > tier1 max {tc['max_diff_lines']}")
    for pat in tc.get("risk_patterns", []):
        rx = re.compile(pat)
        hit = next((l for l in added if rx.search(l)), None)
        if hit is not None:
            reasons.append(f"risk pattern /{pat}/ in added line: {hit.strip()[:80]}")
    gate_ok = True
    if not a.no_gates and proj.cfg["verify"]["gates"]:
        rd = proj.runs / "_check"
        rd.mkdir(parents=True, exist_ok=True)
        gate_ok, results = run_gates(proj.cfg["verify"]["gates"], root, rd, "check", proj,
                                     int(proj.cfg["verify"]["timeout_sec"]))
        if not gate_ok:
            f = results[-1]
            reasons.append(f"gate failed: `{f['cmd']}` rc={f['rc']}\n{tail(f['tail'], 25)}")
    print(f"files={len(changes)} lines={lines}")
    if reasons:
        print("ESCALATE (use a task + `run`, or fix):\n" + bullets(reasons))
        finish("ESCALATE", 1)
    say("tier-1 OK: small, in-scope, gates passed. Commit it yourself.")
    finish("OK", 0)


def print_summary(proj: Project, st: dict) -> None:
    rd = proj.run_dir(st["id"])
    print("-" * 70)
    print(f"task      : {st['id']}  {st.get('title', '')}")
    print(f"status    : {st['status']}")
    print(f"attempts  : {st.get('attempts_total', 0)}   review rounds: {st.get('review_rounds', 0)}")
    if st.get("changed_files"):
        print(f"changed   : {', '.join(st['changed_files'])} ({st.get('diff_lines', 0)} lines)")
    print(f"branch    : {st.get('branch')}   worktree: {st.get('worktree')}")
    if st.get("last_feedback"):
        print(f"feedback  : {tail(st['last_feedback'], 12)}")
    if st.get("review"):
        print(f"review    : {review_notes(st)}")
    nxt = {READY: f"review {rd / 'REVIEW.md'} then `verdict {st['id']} PASS|FAIL --notes ...`",
           APPROVED: f"`merge {st['id']}` (or inspect branch {st.get('branch')} first)",
           REJECTED: f"`revise {st['id']}` (sends review notes to the builder)",
           ESCALATED: "human decision needed: refine the task, split it, or do it by hand",
           BLOCKED: "builder says the task is impossible as specified - fix the task packet",
           BUILDER_ERROR: f"check {rd} logs (quota/auth/permissions), then `run` again",
           MERGED: "done"}.get(st["status"])
    if nxt:
        print(f"next      : {nxt}")
    print(f"result    : {rd / 'RESULT.json'}")
    print("-" * 70)


# --------------------------------------------------------------------------- #
def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(prog="orchestra.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", "-C", default=".", help="path inside the target git repo")
    ap.add_argument("--profile", "-P", default="", help="apply [profiles.<name>] from orchestra.toml")
    ap.add_argument("--version", action="version", version=VERSION)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init"); p.add_argument("--force", action="store_true")
    p = sub.add_parser("new"); p.add_argument("id"); p.add_argument("--title", default="")
    p = sub.add_parser("run"); p.add_argument("task")
    p.add_argument("--hitl", action="store_true", help="human runs the builder")
    p.add_argument("--force-unlock", action="store_true")
    p = sub.add_parser("revise"); p.add_argument("id")
    p.add_argument("--notes", default=""); p.add_argument("--notes-file", default="")
    p.add_argument("--hitl", action="store_true"); p.add_argument("--force-unlock", action="store_true")
    p = sub.add_parser("verdict"); p.add_argument("id")
    p.add_argument("verdict", choices=["PASS", "FAIL", "pass", "fail"])
    p.add_argument("--notes", default=""); p.add_argument("--notes-file", default="")
    p = sub.add_parser("merge"); p.add_argument("id"); p.add_argument("--force", action="store_true")
    p = sub.add_parser("check"); p.add_argument("--no-gates", action="store_true")
    p = sub.add_parser("status"); p.add_argument("id", nargs="?")
    p = sub.add_parser("clean"); p.add_argument("id", nargs="?"); p.add_argument("--all", action="store_true")

    a = ap.parse_args()
    proj = Project(Path(a.project).resolve(), a.profile)
    {"init": cmd_init, "new": cmd_new, "run": cmd_run, "revise": cmd_revise,
     "verdict": cmd_verdict, "merge": cmd_merge, "check": cmd_check,
     "status": cmd_status, "clean": cmd_clean}[a.cmd](proj, a)


if __name__ == "__main__":
    main()
