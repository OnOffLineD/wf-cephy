"""Application auto-updater for WF-Companion (GitHub main branch).

Checks the latest commit on the configured GitHub repository/branch and safely
applies updates in either installation mode:
- Git mode (`.git` present and `git` available): refuses dirty working trees,
  then performs `git fetch` + `git merge --ff-only`.
- Archive/Portable mode (no `.git` or `git` unavailable): downloads and validates
  the branch zip archive, preserves all user/runtime files, backs up overwritten
  files for automatic rollback on any error, writes files atomically, and persists
  the installed commit SHA to `data/app_update_state.json`.
"""
import argparse
import fnmatch
import html
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from scripts.path_config import get_path, get_user_data_path, write_json_atomic

DEFAULT_OWNER = "OnOffLineD"
DEFAULT_REPO = "wf-cephy"
DEFAULT_BRANCH = "main"
USER_AGENT = "WF-Companion/1.0"

COMMIT_API_URL = "https://api.github.com/repos/{owner}/{repo}/commits/{branch}"
COMPARE_API_URL = "https://api.github.com/repos/{owner}/{repo}/compare/{base}...{head}"
ARCHIVE_ZIP_URL = "https://github.com/{owner}/{repo}/archive/refs/heads/{branch}.zip"
COMMIT_WEB_URL = "https://github.com/{owner}/{repo}/commit/{sha}"
COMPARE_WEB_URL = "https://github.com/{owner}/{repo}/compare/{base}...{head}"

DEFAULT_TIMEOUT = 15
DEFAULT_DOWNLOAD_TIMEOUT = 90
CHECK_INTERVAL_SECONDS = 6 * 3600
REPLACE_RETRIES = 5
MAX_LISTED_FILES = 10

_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")

# Directories whose contents are user-owned, runtime-generated, or environment-specific.
PROTECTED_DIR_PREFIXES = (
    ".git",
    "data/chroma_db",
    "data/wiki_cache",
    "data/raw_wfcd",
    "data/logs",
    "python_embed",
    "models",
    "graphify-out",
    "bin",
)

# Individual files / glob patterns preserved during archive updates.
PROTECTED_FILE_PATTERNS = (
    "data/user_*.json",
    "data/user_*.json.*",
    "data/persona_config.json",
    "data/wf_database.sqlite",
    "data/wf_database.sqlite-*",
    "data/app_update_state.json",
    "data/game_data_state.json",
    ".env",
    ".env.*",
)


class AppUpdateError(Exception):
    """Raised internally when an update step fails with a user-facing reason."""

    def __init__(self, message: str, error_kind: str = "update_error"):
        super().__init__(message)
        self.error_kind = error_kind


def _normalize_rel_path(rel_path: str) -> str:
    cleaned = rel_path.replace("\\", "/").strip()
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    return cleaned.lstrip("/")


def is_protected_path(rel_path: str) -> bool:
    """Return True if `rel_path` (relative to project root) must never be overwritten."""
    norm = _normalize_rel_path(rel_path)
    if not norm:
        return True
    lower = norm.lower()
    for prefix in PROTECTED_DIR_PREFIXES:
        p = prefix.lower()
        if lower == p or lower.startswith(p + "/"):
            return True
    for pattern in PROTECTED_FILE_PATTERNS:
        if fnmatch.fnmatch(lower, pattern.lower()):
            return True
    return False


def _write_bytes_atomic(path: str, payload: bytes) -> None:
    """Write bytes to a temp file in the same directory and swap atomically."""
    abs_path = os.path.abspath(path)
    directory = os.path.dirname(abs_path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=f".{os.path.basename(abs_path)}.",
        suffix=".upd.tmp",
        dir=directory,
    )
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
            f.flush()
        for attempt in range(REPLACE_RETRIES):
            try:
                os.replace(tmp_path, abs_path)
                break
            except PermissionError:
                if attempt == REPLACE_RETRIES - 1:
                    raise
                time.sleep(0.05)
    except BaseException:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        raise


def _short_sha(sha: Optional[str]) -> str:
    return sha[:7] if sha else "알 수 없음"


def _first_line(text: str) -> str:
    if not text:
        return ""
    return text.splitlines()[0].strip()


def requirements_install_command(
    python_executable: Optional[str] = None,
    root_dir: Optional[str] = None,
) -> List[str]:
    """Return the pip install command for updating dependencies after requirements.txt changes."""
    exe = python_executable or sys.executable
    req_path = os.path.join(os.path.abspath(root_dir or ROOT_DIR), "requirements.txt")
    return [exe, "-m", "pip", "install", "-r", req_path]


def build_relaunch_command(
    root_dir: Optional[str] = None,
    argv: Optional[List[str]] = None,
    python_executable: Optional[str] = None,
) -> List[str]:
    """Build the command used to cleanly relaunch WF-Companion after an update."""
    base = os.path.abspath(root_dir or ROOT_DIR)
    main_script = os.path.join(base, "main_companion.py")
    if not os.path.isfile(main_script):
        main_script = os.path.join(base, "scripts", "desktop_companion.py")
    raw_args = list(sys.argv[1:] if argv is None else argv)
    forwarded = [a for a in raw_args if a in ("--enable-llm", "--disable-llm")]
    return [python_executable or sys.executable, main_script, *forwarded]


def relaunch_application(
    root_dir: Optional[str] = None,
    argv: Optional[List[str]] = None,
    python_executable: Optional[str] = None,
    before_exit: Optional[Callable[[], None]] = None,
    spawner: Optional[Callable[..., Any]] = None,
    exit_func: Optional[Callable[[], None]] = None,
) -> bool:
    """Stop runtime helpers, launch a fresh companion process, and exit the current one."""
    base = os.path.abspath(root_dir or ROOT_DIR)
    cmd = build_relaunch_command(root_dir=base, argv=argv, python_executable=python_executable)
    if before_exit is not None:
        try:
            before_exit()
        except Exception:
            pass
    spawn = spawner or subprocess.Popen
    kwargs: Dict[str, Any] = {"cwd": base}
    if os.name == "nt":
        flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
        if flags:
            kwargs["creationflags"] = flags
    else:
        kwargs["start_new_session"] = True
    spawn(cmd, **kwargs)
    if exit_func is not None:
        exit_func()
    return True


def _default_git_runner(args: List[str], cwd: str, timeout: int) -> subprocess.CompletedProcess:
    kwargs: Dict[str, Any] = {
        "cwd": cwd,
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "timeout": timeout,
    }
    if os.name == "nt":
        no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if no_window:
            kwargs["creationflags"] = no_window
    return subprocess.run(["git", *args], **kwargs)


class AppUpdater:
    """Checks and applies application updates from GitHub `main` safely."""

    def __init__(
        self,
        root_dir: Optional[str] = None,
        owner: str = DEFAULT_OWNER,
        repo: str = DEFAULT_REPO,
        branch: str = DEFAULT_BRANCH,
        state_path: Optional[str] = None,
        http_get: Optional[Callable[..., Any]] = None,
        git_runner: Optional[Callable[..., subprocess.CompletedProcess]] = None,
        timeout: int = DEFAULT_TIMEOUT,
        download_timeout: int = DEFAULT_DOWNLOAD_TIMEOUT,
    ):
        self._explicit_root = root_dir is not None
        self.root_dir = os.path.abspath(root_dir) if root_dir is not None else ROOT_DIR
        self.owner = owner
        self.repo = repo
        self.branch = branch
        if state_path is not None:
            self.state_path = os.path.abspath(state_path)
        elif self._explicit_root:
            self.state_path = os.path.join(self.root_dir, "data", "app_update_state.json")
        else:
            self.state_path = get_user_data_path("app_update_state.json")
        self._http_get = http_get or requests.get
        self._git_runner = git_runner or _default_git_runner
        self.timeout = timeout
        self.download_timeout = download_timeout

    # ------------------------------------------------------------------
    # State & installation mode helpers
    # ------------------------------------------------------------------
    def _api_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
        }

    def load_state(self) -> Dict[str, Any]:
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def save_state(self, state: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        write_json_atomic(self.state_path, state)

    def due_for_check(self, interval_seconds: int = CHECK_INTERVAL_SECONDS) -> bool:
        last_check = self.load_state().get("last_check", 0)
        try:
            return (time.time() - float(last_check)) >= interval_seconds
        except (TypeError, ValueError):
            return True

    def _run_git(self, args: List[str], timeout: Optional[int] = None) -> subprocess.CompletedProcess:
        return self._git_runner(args, cwd=self.root_dir, timeout=timeout or self.timeout)

    def _has_git_dir(self) -> bool:
        return os.path.exists(os.path.join(self.root_dir, ".git"))

    def detect_mode(self) -> str:
        """Return 'git' if `.git` is present and git works here, else 'archive'."""
        if not self._has_git_dir():
            return "archive"
        try:
            res = self._run_git(["rev-parse", "HEAD"], timeout=min(self.timeout, 10))
            if res.returncode == 0 and _SHA_RE.match((res.stdout or "").strip()):
                return "git"
        except (FileNotFoundError, OSError, subprocess.SubprocessError):
            pass
        return "archive"

    def get_local_sha(self, mode: Optional[str] = None) -> Optional[str]:
        """Detect the installed commit SHA from git HEAD or `data/app_update_state.json`."""
        resolved_mode = mode or self.detect_mode()
        if resolved_mode == "git":
            try:
                res = self._run_git(["rev-parse", "HEAD"], timeout=min(self.timeout, 10))
                sha = (res.stdout or "").strip()
                if res.returncode == 0 and _SHA_RE.match(sha):
                    return sha
            except (FileNotFoundError, OSError, subprocess.SubprocessError):
                return None
            return None
        state = self.load_state()
        for key in ("installed_sha", "commit_sha", "sha"):
            val = state.get(key)
            if isinstance(val, str) and _SHA_RE.match(val.strip()):
                return val.strip()
        return None

    # ------------------------------------------------------------------
    # Remote check
    # ------------------------------------------------------------------
    def _classify_http_error(self, response: Any) -> Tuple[str, str]:
        status = getattr(response, "status_code", None)
        headers = getattr(response, "headers", None) or {}
        remaining = headers.get("X-RateLimit-Remaining") or headers.get("x-ratelimit-remaining")
        detail = ""
        try:
            body = response.json()
            if isinstance(body, dict) and body.get("message"):
                detail = str(body["message"])
        except Exception:
            detail = ""

        if status in (403, 429) and (remaining == "0" or "rate limit" in detail.lower() or status == 429):
            return (
                "rate_limit",
                "GitHub API 요청 한도를 초과했습니다. 잠시 후 다시 시도해 주세요.",
            )
        if status == 404:
            return (
                "not_found",
                f"GitHub 저장소 또는 브랜치({self.owner}/{self.repo}@{self.branch})를 찾을 수 없습니다.",
            )
        msg = f"GitHub 서버 오류 (HTTP {status})"
        if detail:
            msg += f": {detail}"
        return ("http_error", msg)

    def _fetch_compare_info(self, local_sha: str, remote_sha: str) -> Optional[Dict[str, Any]]:
        url = COMPARE_API_URL.format(
            owner=self.owner,
            repo=self.repo,
            base=local_sha,
            head=remote_sha,
        )
        try:
            resp = self._http_get(url, headers=self._api_headers(), timeout=self.timeout)
            if getattr(resp, "status_code", 200) != 200:
                return None
            data = resp.json()
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    def check(self) -> Dict[str, Any]:
        """Check GitHub for a newer commit on the configured branch.

        Never raises on network/HTTP/rate-limit failures; returns a structured dict
        with `ok=False` and a clear Korean `error` message.
        """
        mode = self.detect_mode()
        local_sha = self.get_local_sha(mode=mode)
        base_result: Dict[str, Any] = {
            "ok": False,
            "error": None,
            "error_kind": None,
            "update_available": False,
            "local_sha": local_sha,
            "remote_sha": None,
            "commit_message": "",
            "commit_title": "",
            "commit_date": "",
            "commit_author": "",
            "behind_count": None,
            "ahead_count": None,
            "diverged": False,
            "compare_url": "",
            "mode": mode,
            "branch": self.branch,
            "repo": f"{self.owner}/{self.repo}",
        }

        url = COMMIT_API_URL.format(owner=self.owner, repo=self.repo, branch=self.branch)
        try:
            resp = self._http_get(url, headers=self._api_headers(), timeout=self.timeout)
        except requests.Timeout:
            base_result["error_kind"] = "timeout"
            base_result["error"] = "GitHub 서버 응답 시간이 초과되었습니다. 네트워크 상태를 확인해 주세요."
            return base_result
        except requests.ConnectionError:
            base_result["error_kind"] = "offline"
            base_result["error"] = "네트워크 연결에 실패했습니다. 인터넷 연결 상태를 확인해 주세요."
            return base_result
        except requests.RequestException as exc:
            base_result["error_kind"] = "network_error"
            base_result["error"] = f"업데이트 확인 중 네트워크 오류가 발생했습니다: {exc}"
            return base_result
        except Exception as exc:
            base_result["error_kind"] = "network_error"
            base_result["error"] = f"업데이트 확인 중 오류가 발생했습니다: {exc}"
            return base_result

        status_code = getattr(resp, "status_code", 200)
        if status_code >= 400:
            kind, msg = self._classify_http_error(resp)
            base_result["error_kind"] = kind
            base_result["error"] = msg
            return base_result

        try:
            payload = resp.json()
        except Exception:
            base_result["error_kind"] = "invalid_response"
            base_result["error"] = "GitHub 응답을 JSON으로 해석하지 못했습니다."
            return base_result

        if not isinstance(payload, dict) or not isinstance(payload.get("sha"), str) or not _SHA_RE.match(payload["sha"].strip()):
            base_result["error_kind"] = "invalid_response"
            base_result["error"] = "GitHub 커밋 응답 형식이 올바르지 않습니다."
            return base_result

        remote_sha = payload["sha"].strip()
        commit_obj = payload.get("commit") if isinstance(payload.get("commit"), dict) else {}
        commit_message = str(commit_obj.get("message") or "").strip()
        committer = commit_obj.get("committer") if isinstance(commit_obj.get("committer"), dict) else {}
        author = commit_obj.get("author") if isinstance(commit_obj.get("author"), dict) else {}
        commit_date = str(committer.get("date") or author.get("date") or "")
        commit_author = str(author.get("name") or committer.get("name") or "")
        commit_url = str(
            payload.get("html_url")
            or COMMIT_WEB_URL.format(owner=self.owner, repo=self.repo, sha=remote_sha)
        )

        behind_count: Optional[int] = None
        ahead_count: Optional[int] = None
        diverged = False
        compare_url = commit_url

        if local_sha and local_sha.lower() == remote_sha.lower():
            update_available = False
            behind_count = 0
            ahead_count = 0
        elif local_sha:
            compare_url = COMPARE_WEB_URL.format(
                owner=self.owner,
                repo=self.repo,
                base=local_sha[:7],
                head=remote_sha[:7],
            )
            cmp_data = self._fetch_compare_info(local_sha, remote_sha)
            if cmp_data is not None:
                if isinstance(cmp_data.get("html_url"), str) and cmp_data["html_url"]:
                    compare_url = cmp_data["html_url"]
                cmp_status = str(cmp_data.get("status") or "")
                # Base=local, head=remote: ahead_by is how many commits remote is ahead of local.
                if isinstance(cmp_data.get("ahead_by"), int):
                    behind_count = cmp_data["ahead_by"]
                if isinstance(cmp_data.get("behind_by"), int):
                    ahead_count = cmp_data["behind_by"]
                if cmp_status == "identical":
                    update_available = False
                    behind_count = 0
                elif cmp_status == "behind" and (behind_count == 0):
                    # Local has unpushed commits ahead of remote; remote has no new commits.
                    update_available = False
                elif cmp_status == "diverged":
                    update_available = bool(behind_count is None or behind_count > 0)
                    diverged = True
                else:
                    update_available = bool(behind_count is None or behind_count > 0)
            else:
                update_available = True
        else:
            # Portable installation without a recorded commit SHA yet.
            update_available = True

        base_result.update(
            {
                "ok": True,
                "update_available": update_available,
                "remote_sha": remote_sha,
                "commit_message": commit_message,
                "commit_title": _first_line(commit_message),
                "commit_date": commit_date,
                "commit_author": commit_author,
                "behind_count": behind_count,
                "ahead_count": ahead_count,
                "diverged": diverged,
                "compare_url": compare_url,
            }
        )
        return base_result

    # ------------------------------------------------------------------
    # Applying updates
    # ------------------------------------------------------------------
    def _empty_apply_result(self, mode: str, previous_sha: Optional[str]) -> Dict[str, Any]:
        return {
            "ok": False,
            "updated": False,
            "mode": mode,
            "previous_sha": previous_sha,
            "new_sha": previous_sha,
            "updated_files": [],
            "requirements_changed": False,
            "rolled_back": False,
            "restart_recommended": False,
            "dirty_files": [],
            "message": "",
            "error": None,
            "error_kind": None,
        }

    def apply(
        self,
        check_info: Optional[Dict[str, Any]] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """Safely apply updates according to the detected installation mode."""
        mode = self.detect_mode()
        if mode == "git":
            return self._apply_git(check_info=check_info)
        return self._apply_archive(check_info=check_info, force=force)

    # --- Git mode ---
    def _get_dirty_files(self) -> Tuple[bool, List[str], Optional[str]]:
        try:
            res = self._run_git(["status", "--porcelain"], timeout=self.timeout)
        except subprocess.TimeoutExpired:
            return False, [], "git 상태 확인 시간이 초과되었습니다."
        except (FileNotFoundError, OSError, subprocess.SubprocessError) as exc:
            return False, [], f"git 상태 확인에 실패했습니다: {exc}"

        if res.returncode != 0:
            err = (res.stderr or res.stdout or "").strip()
            return False, [], f"git 상태 확인 실패: {err or '알 수 없는 오류'}"

        dirty: List[str] = []
        for raw_line in (res.stdout or "").splitlines():
            if not raw_line.strip():
                continue
            status_code = raw_line[:2]
            path_part = raw_line[3:].strip().strip('"').replace("\\", "/")
            # Ignore our own untracked state file if present.
            if status_code == "??" and path_part.lower() == "data/app_update_state.json":
                continue
            dirty.append(path_part or raw_line.strip())
        return True, dirty, None

    def _apply_git(self, check_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        before_sha = self.get_local_sha(mode="git")
        result = self._empty_apply_result("git", before_sha)

        # 1. Refuse dirty working tree before touching anything.
        ok, dirty_files, status_err = self._get_dirty_files()
        if not ok:
            result["error_kind"] = "git_error"
            result["error"] = status_err
            result["message"] = status_err or "git 상태 확인 실패"
            return result
        if dirty_files:
            preview = ", ".join(dirty_files[:5])
            extra = f" 외 {len(dirty_files) - 5}개" if len(dirty_files) > 5 else ""
            msg = (
                "커밋되지 않은 로컬 변경 사항이 있어 자동 업데이트를 중단했습니다 "
                f"({preview}{extra}). 변경 사항을 커밋하거나 보관한 뒤 다시 시도해 주세요."
            )
            result["dirty_files"] = dirty_files
            result["error_kind"] = "dirty_worktree"
            result["error"] = msg
            result["message"] = msg
            return result

        # 2. Verify active branch matches target branch (avoid unexpected merges on feature branches).
        try:
            br_res = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"], timeout=self.timeout)
            current_branch = (br_res.stdout or "").strip() if br_res.returncode == 0 else ""
        except (OSError, subprocess.SubprocessError):
            current_branch = ""
        if current_branch == "HEAD":
            msg = f"현재 Git 저장소가 detached HEAD 상태입니다. '{self.branch}' 브랜치로 전환한 뒤 업데이트해 주세요."
            result["error_kind"] = "detached_head"
            result["error"] = msg
            result["message"] = msg
            return result
        if current_branch and current_branch != self.branch:
            msg = f"현재 브랜치('{current_branch}')가 '{self.branch}'가 아닙니다. '{self.branch}' 브랜치에서 업데이트해 주세요."
            result["error_kind"] = "wrong_branch"
            result["error"] = msg
            result["message"] = msg
            return result

        # 3. Fetch remote branch.
        try:
            fetch_res = self._run_git(["fetch", "origin", self.branch], timeout=self.download_timeout)
        except subprocess.TimeoutExpired:
            msg = "git fetch 시간이 초과되었습니다. 네트워크 상태를 확인해 주세요."
            result["error_kind"] = "timeout"
            result["error"] = msg
            result["message"] = msg
            return result
        except (FileNotFoundError, OSError, subprocess.SubprocessError) as exc:
            msg = f"git fetch 실행 중 오류가 발생했습니다: {exc}"
            result["error_kind"] = "git_fetch_failed"
            result["error"] = msg
            result["message"] = msg
            return result

        if fetch_res.returncode != 0:
            err = (fetch_res.stderr or fetch_res.stdout or "").strip()
            msg = f"원격 저장소에서 최신 변경을 가져오지 못했습니다: {err or 'git fetch 실패'}"
            result["error_kind"] = "git_fetch_failed"
            result["error"] = msg
            result["message"] = msg
            return result

        # 4. Fast-forward merge only (never rewrites or discards local commits).
        target_ref = f"origin/{self.branch}"
        try:
            merge_res = self._run_git(["merge", "--ff-only", target_ref], timeout=self.timeout)
        except subprocess.TimeoutExpired:
            msg = "git merge 시간이 초과되었습니다."
            result["error_kind"] = "timeout"
            result["error"] = msg
            result["message"] = msg
            return result
        except (FileNotFoundError, OSError, subprocess.SubprocessError) as exc:
            msg = f"git merge 실행 중 오류가 발생했습니다: {exc}"
            result["error_kind"] = "git_merge_failed"
            result["error"] = msg
            result["message"] = msg
            return result

        if merge_res.returncode != 0:
            err = (merge_res.stderr or merge_res.stdout or "").strip()
            lower_err = err.lower()
            is_non_ff = (
                "not possible to fast-forward" in lower_err
                or "fast-forward" in lower_err
                or "diverging" in lower_err
                or "fatal: refusing to merge" in lower_err
            )
            result["error_kind"] = "non_fast_forward" if is_non_ff else "git_merge_failed"
            if is_non_ff:
                msg = (
                    f"로컬 브랜치가 원격 {target_ref} 브랜치와 분기되어 Fast-Forward 업데이트를 수행할 수 없습니다. "
                    "수동으로 병합한 뒤 다시 시도해 주세요."
                )
            else:
                msg = f"Fast-Forward 병합에 실패했습니다: {err or '알 수 없는 오류'}"
            result["error"] = msg
            result["message"] = msg
            return result

        new_sha = self.get_local_sha(mode="git") or before_sha
        updated = bool(new_sha and before_sha and new_sha.lower() != before_sha.lower())
        updated_files: List[str] = []
        if updated and before_sha and new_sha:
            try:
                diff_res = self._run_git(["diff", "--name-only", before_sha, new_sha], timeout=self.timeout)
                if diff_res.returncode == 0:
                    updated_files = [
                        _normalize_rel_path(line)
                        for line in (diff_res.stdout or "").splitlines()
                        if line.strip()
                    ]
            except (OSError, subprocess.SubprocessError):
                updated_files = []

        req_changed = any(p.lower() == "requirements.txt" for p in updated_files)
        result.update(
            {
                "ok": True,
                "updated": updated,
                "new_sha": new_sha,
                "updated_files": updated_files,
                "requirements_changed": req_changed,
                "restart_recommended": updated,
                "message": (
                    f"Git Fast-Forward 업데이트 완료 ({_short_sha(before_sha)} → {_short_sha(new_sha)}, "
                    f"변경 파일 {len(updated_files)}개)."
                    if updated
                    else "이미 최신 버전입니다."
                ),
            }
        )
        return result

    # --- Archive / Portable mode ---
    def _parse_and_validate_archive(self, zip_bytes: bytes) -> List[Tuple[str, bytes]]:
        """Validate zip integrity, block path traversal/symlinks, strip GitHub root prefix."""
        try:
            zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
        except zipfile.BadZipFile as exc:
            raise AppUpdateError(f"다운로드한 업데이트 파일이 올바른 ZIP 아카이브가 아닙니다: {exc}", "invalid_archive")

        with zf:
            bad_member = zf.testzip()
            if bad_member is not None:
                raise AppUpdateError(f"ZIP 아카이브가 손상되었습니다 (손상 항목: {bad_member}).", "invalid_archive")

            infos = [info for info in zf.infolist() if info.filename != "pax_global_header"]
            if not infos:
                raise AppUpdateError("ZIP 아카이브가 비어 있습니다.", "invalid_archive")

            # Validate raw paths before prefix stripping so traversal can never hide behind a prefix.
            top_segments = set()
            for info in infos:
                raw_name = info.filename
                if "\\" in raw_name:
                    raw_name_check = raw_name.replace("\\", "/")
                else:
                    raw_name_check = raw_name
                if raw_name_check.startswith("/") or re.match(r"^[A-Za-z]:", raw_name_check):
                    raise AppUpdateError(f"허용되지 않는 절대 경로가 포함된 아카이브입니다: {info.filename}", "invalid_archive")
                parts = [p for p in raw_name_check.split("/") if p not in ("", ".")]
                if any(p == ".." for p in parts):
                    raise AppUpdateError(f"허용되지 않는 상위 경로(..)가 포함된 아카이브입니다: {info.filename}", "invalid_archive")
                if parts:
                    top_segments.add(parts[0])

            # GitHub branch archives place everything inside `<repo>-<branch>/`.
            top_only = next(iter(top_segments)) if len(top_segments) == 1 else ""
            strip_prefix = (
                len(top_segments) == 1
                and top_only.lower() not in {"scripts", "data", "assets", "rules", "tests"}
                and any(
                    len([p for p in info.filename.replace("\\", "/").split("/") if p not in ("", ".")]) >= 2
                    for info in infos
                )
            )

            real_root = os.path.realpath(self.root_dir)
            extracted: List[Tuple[str, bytes]] = []
            for info in infos:
                if info.is_dir():
                    continue
                # Skip symlinks inside archives for safety.
                unix_mode = (info.external_attr >> 16) & 0o170000
                if unix_mode == stat.S_IFLNK:
                    continue

                raw_norm = info.filename.replace("\\", "/")
                parts = [p for p in raw_norm.split("/") if p not in ("", ".")]
                if strip_prefix:
                    parts = parts[1:]
                if not parts:
                    continue
                if any(p == ".." for p in parts):
                    raise AppUpdateError(f"허용되지 않는 경로가 포함된 아카이브입니다: {info.filename}", "invalid_archive")

                rel_path = "/".join(parts)
                dest_abs = os.path.abspath(os.path.join(real_root, *parts))
                try:
                    if os.path.commonpath([real_root, dest_abs]) != real_root:
                        raise AppUpdateError(f"프로젝트 외부 경로를 가리키는 아카이브입니다: {info.filename}", "invalid_archive")
                except ValueError:
                    raise AppUpdateError(f"잘못된 드라이브 경로가 포함된 아카이브입니다: {info.filename}", "invalid_archive")

                extracted.append((rel_path, zf.read(info)))

        if not extracted:
            raise AppUpdateError("ZIP 아카이브에 추출할 파일이 없습니다.", "invalid_archive")
        return extracted

    @staticmethod
    def _rollback_archive(
        backups: List[Tuple[str, str]],
        created_files: List[str],
        created_dirs: List[str],
    ) -> None:
        for path in reversed(created_files):
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass
        for dest_path, backup_path in reversed(backups):
            try:
                with open(backup_path, "rb") as f:
                    original_bytes = f.read()
                _write_bytes_atomic(dest_path, original_bytes)
            except OSError:
                try:
                    shutil.copy2(backup_path, dest_path)
                except OSError:
                    pass
        for d in reversed(created_dirs):
            try:
                if os.path.isdir(d) and not os.listdir(d):
                    os.rmdir(d)
            except OSError:
                pass

    def _apply_archive(
        self,
        check_info: Optional[Dict[str, Any]] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        local_sha = self.get_local_sha(mode="archive")
        result = self._empty_apply_result("archive", local_sha)

        info = check_info if (isinstance(check_info, dict) and check_info.get("ok") and check_info.get("remote_sha")) else self.check()
        if not info.get("ok"):
            result["error_kind"] = info.get("error_kind") or "check_failed"
            result["error"] = info.get("error") or "업데이트 정보를 확인하지 못했습니다."
            result["message"] = result["error"]
            return result

        remote_sha = info.get("remote_sha")
        if not force and local_sha and remote_sha and local_sha.lower() == remote_sha.lower():
            result.update(
                {
                    "ok": True,
                    "updated": False,
                    "new_sha": remote_sha,
                    "message": "이미 최신 버전입니다.",
                }
            )
            return result

        zip_url = ARCHIVE_ZIP_URL.format(owner=self.owner, repo=self.repo, branch=self.branch)
        try:
            resp = self._http_get(
                zip_url,
                headers={"User-Agent": USER_AGENT},
                timeout=self.download_timeout,
            )
        except requests.Timeout:
            msg = "업데이트 아카이브 다운로드 시간이 초과되었습니다."
            result["error_kind"] = "timeout"
            result["error"] = msg
            result["message"] = msg
            return result
        except requests.ConnectionError:
            msg = "네트워크 연결에 실패하여 아카이브를 다운로드하지 못했습니다."
            result["error_kind"] = "offline"
            result["error"] = msg
            result["message"] = msg
            return result
        except requests.RequestException as exc:
            msg = f"업데이트 아카이브 다운로드 실패: {exc}"
            result["error_kind"] = "download_error"
            result["error"] = msg
            result["message"] = msg
            return result
        except Exception as exc:
            msg = f"업데이트 아카이브 다운로드 오류: {exc}"
            result["error_kind"] = "download_error"
            result["error"] = msg
            result["message"] = msg
            return result

        status_code = getattr(resp, "status_code", 200)
        if status_code >= 400:
            kind, msg = self._classify_http_error(resp)
            result["error_kind"] = kind
            result["error"] = msg
            result["message"] = msg
            return result

        zip_bytes = getattr(resp, "content", b"")
        try:
            entries = self._parse_and_validate_archive(zip_bytes)
        except AppUpdateError as exc:
            result["error_kind"] = exc.error_kind
            result["error"] = str(exc)
            result["message"] = str(exc)
            return result

        # Filter out protected user/runtime files and unchanged files.
        plan: List[Tuple[str, str, bytes]] = []
        for rel_path, content in entries:
            if is_protected_path(rel_path):
                continue
            dest_path = os.path.abspath(os.path.join(self.root_dir, *rel_path.split("/")))
            if os.path.isfile(dest_path):
                try:
                    with open(dest_path, "rb") as existing_f:
                        if existing_f.read() == content:
                            continue
                except OSError:
                    pass
            plan.append((rel_path, dest_path, content))

        backup_dir = tempfile.mkdtemp(prefix="wf_app_update_backup_")
        backups: List[Tuple[str, str]] = []
        created_files: List[str] = []
        created_dirs: List[str] = []
        written_files: List[str] = []

        try:
            for idx, (rel_path, dest_path, content) in enumerate(plan):
                parent = os.path.dirname(dest_path)
                if parent and not os.path.isdir(parent):
                    # Record newly created directory levels for clean rollback.
                    missing_levels = []
                    cur = parent
                    while cur and not os.path.exists(cur) and os.path.abspath(cur) != os.path.abspath(self.root_dir):
                        missing_levels.append(cur)
                        nxt = os.path.dirname(cur)
                        if nxt == cur:
                            break
                        cur = nxt
                    os.makedirs(parent, exist_ok=True)
                    for lvl in reversed(missing_levels):
                        if lvl not in created_dirs:
                            created_dirs.append(lvl)

                existed = os.path.isfile(dest_path)
                if existed:
                    backup_path = os.path.join(backup_dir, f"{idx}_{os.path.basename(dest_path)}")
                    shutil.copy2(dest_path, backup_path)
                    backups.append((dest_path, backup_path))

                _write_bytes_atomic(dest_path, content)
                if not existed:
                    created_files.append(dest_path)
                written_files.append(rel_path)

            # Persist installed commit SHA atomically only after all files succeed.
            state = self.load_state()
            state.update(
                {
                    "installed_sha": remote_sha,
                    "branch": self.branch,
                    "owner": self.owner,
                    "repo": self.repo,
                    "commit_message": info.get("commit_message", ""),
                    "commit_date": info.get("commit_date", ""),
                    "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "mode": "archive",
                }
            )
            self.save_state(state)
        except Exception as exc:
            self._rollback_archive(backups, created_files, created_dirs)
            msg = f"아카이브 업데이트 적용 중 오류가 발생하여 이전 상태로 자동 복구했습니다: {exc}"
            result["rolled_back"] = True
            result["error_kind"] = "apply_error"
            result["error"] = msg
            result["message"] = msg
            return result
        finally:
            shutil.rmtree(backup_dir, ignore_errors=True)

        req_changed = any(p.lower() == "requirements.txt" for p in written_files)
        changed = bool(written_files) or (local_sha != remote_sha)
        result.update(
            {
                "ok": True,
                "updated": changed,
                "new_sha": remote_sha,
                "updated_files": written_files,
                "requirements_changed": req_changed,
                "rolled_back": False,
                "restart_recommended": bool(written_files),
                "message": (
                    f"포터블 아카이브 업데이트 완료 ({_short_sha(local_sha)} → {_short_sha(remote_sha)}, "
                    f"갱신 파일 {len(written_files)}개). 사용자 데이터는 그대로 보존되었습니다."
                    if changed
                    else "이미 최신 버전입니다."
                ),
            }
        )
        return result


def format_check_summary(info: Dict[str, Any]) -> str:
    """Format an update check result dict into concise Korean text."""
    if not info.get("ok"):
        return f"⚠️ 업데이트 확인 실패: {info.get('error') or '알 수 없는 오류'}"

    mode_label = "Git 저장소" if info.get("mode") == "git" else "포터블 아카이브"
    local_s = _short_sha(info.get("local_sha"))
    remote_s = _short_sha(info.get("remote_sha"))
    title = info.get("commit_title") or _first_line(info.get("commit_message", "")) or "(커밋 메시지 없음)"
    date_s = (info.get("commit_date") or "").replace("T", " ").replace("Z", " UTC")

    if not info.get("update_available"):
        lines = [
            f"✅ 현재 최신 버전입니다. ({info.get('repo')}@{info.get('branch')})",
            f"• 현재 커밋: {local_s} ({mode_label})",
            f"• 최신 커밋: {title}",
        ]
        if info.get("ahead_count"):
            lines.append(f"• 참고: 로컬에 원격보다 앞선 커밋이 {info['ahead_count']}개 있습니다.")
        return "\n".join(lines)

    behind = info.get("behind_count")
    behind_str = f" ({behind}개 커밋 뒤처짐)" if isinstance(behind, int) and behind > 0 else ""
    lines = [
        f"🆕 새 앱 업데이트가 있습니다!{behind_str}",
        f"• 설치 방식: {mode_label}",
        f"• 현재 버전: {local_s} → 최신 버전: {remote_s}",
        f"• 최신 커밋: {title}",
    ]
    if date_s:
        lines.append(f"• 커밋 일시: {date_s}")
    if info.get("compare_url"):
        lines.append(f"• 변경 비교: {info['compare_url']}")
    return "\n".join(lines)


def format_apply_summary(result: Dict[str, Any]) -> str:
    """Format an update apply result dict into concise Korean text."""
    if not result.get("ok"):
        prefix = "⚠️ 업데이트 실패 (자동 복구 완료): " if result.get("rolled_back") else "⚠️ 업데이트 실패: "
        return prefix + (result.get("error") or result.get("message") or "알 수 없는 오류")

    if not result.get("updated"):
        return "✅ 이미 최신 버전입니다. 변경된 파일이 없습니다."

    files = result.get("updated_files") or []
    preview = ", ".join(files[:MAX_LISTED_FILES])
    extra = f" 외 {len(files) - MAX_LISTED_FILES}개" if len(files) > MAX_LISTED_FILES else ""
    lines = [
        f"✅ {result.get('message') or '업데이트가 완료되었습니다.'}",
        f"• 버전: {_short_sha(result.get('previous_sha'))} → {_short_sha(result.get('new_sha'))}",
    ]
    if files:
        lines.append(f"• 변경 파일 ({len(files)}개): {preview}{extra}")
    if result.get("requirements_changed"):
        lines.append("• ⚠️ requirements.txt가 변경되었습니다. 필요 시 `pip install -r requirements.txt`를 실행해 주세요.")
    if result.get("restart_recommended"):
        lines.append("• 변경 사항을 반영하려면 앱을 재시작해 주세요.")
    return "\n".join(lines)


# ----------------------------------------------------------------------
# Optional Qt Frameless Dialog (Warframe Dark HUD Theme)
# ----------------------------------------------------------------------
try:
    from PyQt6.QtCore import Qt, pyqtSignal
    from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
    _HAS_QT = True
except ImportError:
    try:
        from PySide6.QtCore import Qt, Signal as pyqtSignal
        from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
        _HAS_QT = True
    except ImportError:
        _HAS_QT = False

if _HAS_QT:
    from scripts.frameless_dialog import FramelessDialog

    class AppUpdateDialog(FramelessDialog):
        """Frameless Warframe-themed dialog for non-blocking app update check & apply."""

        check_finished_signal = pyqtSignal(dict)
        apply_finished_signal = pyqtSignal(dict)

        def __init__(
            self,
            updater: Optional[AppUpdater] = None,
            initial_check: Optional[Dict[str, Any]] = None,
            on_restart: Optional[Callable[[], None]] = None,
            parent=None,
            auto_check: bool = True,
        ):
            super().__init__(parent)
            self.updater = updater or AppUpdater()
            self.on_restart = on_restart
            self._last_check: Optional[Dict[str, Any]] = initial_check
            self._last_apply: Optional[Dict[str, Any]] = None
            self._busy = False
            self._applying = False
            self._init_ui()
            self.check_finished_signal.connect(self._on_check_finished)
            self.apply_finished_signal.connect(self._on_apply_finished)
            if initial_check is not None:
                self._on_check_finished(initial_check)
            elif auto_check:
                self.start_check()

        def _init_ui(self):
            self.setWindowTitle("앱 업데이트 (GitHub main)")
            self.setFixedWidth(480)
            self.setMinimumHeight(340)

            root = QVBoxLayout(self)
            root.setContentsMargins(12, 10, 12, 12)
            root.setSpacing(10)

            header = self.create_title_bar(
                title="앱 업데이트 (GitHub main)",
                on_close=self._handle_close,
                icon_name="refresh",
            )
            root.addWidget(header)

            self.lbl_status = QLabel("업데이트 상태를 확인하는 중입니다...")
            self.lbl_status.setWordWrap(True)
            self.lbl_status.setStyleSheet("color: #00e5ff; font-size: 13px; font-weight: bold;")
            root.addWidget(self.lbl_status)

            details_card = QFrame()
            details_card.setStyleSheet(
                "QFrame { background-color: #111722; border: 1px solid #1e293b; border-radius: 10px; }"
            )
            details_layout = QVBoxLayout(details_card)
            details_layout.setContentsMargins(12, 10, 12, 10)
            self.lbl_details = QLabel("GitHub 저장소의 최신 커밋 정보를 불러오고 있습니다.")
            self.lbl_details.setWordWrap(True)
            self.lbl_details.setTextFormat(Qt.TextFormat.RichText)
            self.lbl_details.setOpenExternalLinks(True)
            self.lbl_details.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
            self.lbl_details.setStyleSheet("color: #e2e8f0; font-size: 12px; border: none; background: transparent;")
            details_layout.addWidget(self.lbl_details)
            root.addWidget(details_card)

            # Inline confirmation box (shown before applying an update).
            self.confirm_frame = QFrame()
            self.confirm_frame.setStyleSheet(
                "QFrame { background-color: #172033; border: 1px solid #00d2ff; border-radius: 10px; }"
            )
            cf_layout = QVBoxLayout(self.confirm_frame)
            cf_layout.setContentsMargins(12, 10, 12, 10)
            cf_layout.setSpacing(8)
            self.lbl_confirm = QLabel("")
            self.lbl_confirm.setWordWrap(True)
            self.lbl_confirm.setStyleSheet("color: #f8fafc; font-size: 12px; border: none; background: transparent;")
            cf_layout.addWidget(self.lbl_confirm)

            cf_btns = QHBoxLayout()
            cf_btns.addStretch()
            self.btn_cancel_confirm = QPushButton("취소")
            self.btn_cancel_confirm.clicked.connect(self._cancel_apply_confirmation)
            self.btn_confirm_apply = QPushButton("확인 - 지금 업데이트")
            self.btn_confirm_apply.setStyleSheet(
                "QPushButton { background-color: #059669; color: #ffffff; border: none; padding: 7px 14px; border-radius: 6px; font-weight: bold; }"
                "QPushButton:hover { background-color: #10b981; }"
            )
            self.btn_confirm_apply.clicked.connect(self.start_apply)
            cf_btns.addWidget(self.btn_cancel_confirm)
            cf_btns.addWidget(self.btn_confirm_apply)
            cf_layout.addLayout(cf_btns)
            self.confirm_frame.hide()
            root.addWidget(self.confirm_frame)

            # Result / restart prompt box.
            self.result_frame = QFrame()
            self.result_frame.setStyleSheet(
                "QFrame { background-color: #10202e; border: 1px solid #22c55e; border-radius: 10px; }"
            )
            rf_layout = QVBoxLayout(self.result_frame)
            rf_layout.setContentsMargins(12, 10, 12, 10)
            rf_layout.setSpacing(6)
            self.lbl_result = QLabel("")
            self.lbl_result.setWordWrap(True)
            self.lbl_result.setStyleSheet("color: #e2e8f0; font-size: 12px; border: none; background: transparent;")
            rf_layout.addWidget(self.lbl_result)
            self.result_frame.hide()
            root.addWidget(self.result_frame)

            root.addStretch()

            btn_row = QHBoxLayout()
            btn_row.setSpacing(8)
            self.btn_check = QPushButton("다시 확인")
            self.btn_check.clicked.connect(self.start_check)
            self.btn_apply = QPushButton("업데이트 적용")
            self.btn_apply.setEnabled(False)
            self.btn_apply.setStyleSheet(
                "QPushButton { background-color: #0088cc; color: #ffffff; border: none; padding: 8px 14px; border-radius: 6px; font-weight: bold; }"
                "QPushButton:hover { background-color: #00aaff; }"
                "QPushButton:disabled { background-color: #1e293b; color: #64748b; }"
            )
            self.btn_apply.clicked.connect(self._request_apply_confirmation)
            self.btn_restart = QPushButton("지금 재시작")
            self.btn_restart.setStyleSheet(
                "QPushButton { background-color: #d97706; color: #ffffff; border: none; padding: 8px 14px; border-radius: 6px; font-weight: bold; }"
                "QPushButton:hover { background-color: #f59e0b; }"
            )
            self.btn_restart.clicked.connect(self._handle_restart)
            self.btn_restart.hide()
            self.btn_close = QPushButton("닫기")
            self.btn_close.clicked.connect(self._handle_close)

            btn_row.addWidget(self.btn_check)
            btn_row.addStretch()
            btn_row.addWidget(self.btn_apply)
            btn_row.addWidget(self.btn_restart)
            btn_row.addWidget(self.btn_close)
            root.addLayout(btn_row)

        def _handle_close(self):
            if self._applying:
                return
            self.reject()

        def reject(self):
            if self._applying:
                return
            super().reject()

        def closeEvent(self, event):
            if self._applying:
                event.ignore()
                return
            super().closeEvent(event)

        def _set_busy(self, busy: bool, applying: bool = False):
            self._busy = busy
            self._applying = applying
            self.btn_check.setEnabled(not busy)
            self.btn_close.setEnabled(not applying)
            if busy:
                self.btn_apply.setEnabled(False)
                self.confirm_frame.hide()

        def start_check(self):
            if self._busy:
                return
            self._set_busy(True, applying=False)
            self.result_frame.hide()
            self.btn_restart.hide()
            self.lbl_status.setText("GitHub main 브랜치 최신 커밋을 확인 중입니다...")
            self.lbl_details.setText("네트워크 요청을 기다리고 있습니다...")

            def worker():
                try:
                    info = self.updater.check()
                except Exception as exc:
                    info = {"ok": False, "error": str(exc), "update_available": False}
                try:
                    self.check_finished_signal.emit(info)
                except RuntimeError:
                    pass

            threading.Thread(target=worker, daemon=True).start()

        def _render_check_details(self, info: Dict[str, Any]) -> str:
            mode_label = "Git 저장소" if info.get("mode") == "git" else "포터블 아카이브"
            local_s = html.escape(_short_sha(info.get("local_sha")))
            remote_s = html.escape(_short_sha(info.get("remote_sha")))
            title = html.escape(info.get("commit_title") or _first_line(info.get("commit_message", "")) or "(커밋 메시지 없음)")
            date_s = html.escape((info.get("commit_date") or "").replace("T", " ").replace("Z", " UTC"))
            author = html.escape(info.get("commit_author") or "")
            behind = info.get("behind_count")
            lines = [
                f"<b>저장소:</b> {html.escape(str(info.get('repo', '')))} ({html.escape(str(info.get('branch', '')))})",
                f"<b>설치 방식:</b> {mode_label}",
                f"<b>버전:</b> <code>{local_s}</code> → <code>{remote_s}</code>",
                f"<b>최신 커밋:</b> {title}",
            ]
            if author or date_s:
                meta = " · ".join(p for p in (author, date_s) if p)
                lines.append(f"<b>커밋 정보:</b> {meta}")
            if isinstance(behind, int) and behind > 0:
                lines.append(f"<b>누적 변경:</b> {behind}개 커밋 뒤처짐")
            url = info.get("compare_url") or ""
            if url.startswith("https://"):
                safe_url = html.escape(url, quote=True)
                lines.append(f"<b>변경 내역:</b> <a href='{safe_url}' style='color:#38bdf8;'>GitHub에서 비교 보기</a>")
            return "<br>".join(lines)

        def _on_check_finished(self, info: Dict[str, Any]):
            self._last_check = info
            self._set_busy(False, applying=False)
            if not info.get("ok"):
                self.lbl_status.setText("업데이트 확인에 실패했습니다.")
                self.lbl_details.setText(html.escape(str(info.get("error") or "알 수 없는 오류")))
                self.btn_apply.setEnabled(False)
                return

            self.lbl_details.setText(self._render_check_details(info))
            if info.get("update_available"):
                self.lbl_status.setText("새 앱 업데이트를 적용할 수 있습니다.")
                self.btn_apply.setEnabled(True)
            else:
                self.lbl_status.setText("현재 최신 버전을 사용 중입니다.")
                self.btn_apply.setEnabled(False)

        def _request_apply_confirmation(self):
            if self._busy or not self._last_check or not self._last_check.get("update_available"):
                return
            info = self._last_check
            title = info.get("commit_title") or _first_line(info.get("commit_message", ""))
            mode_note = (
                "Git Fast-Forward 방식으로 반영합니다. 커밋되지 않은 변경 사항이 있으면 안전하게 중단됩니다."
                if info.get("mode") == "git"
                else "아카이브를 다운로드해 적용합니다. 사용자 데이터·설정·모델 파일은 보존되며, 실패 시 자동 복구됩니다."
            )
            self.lbl_confirm.setText(
                f"최신 커밋 ({_short_sha(info.get('remote_sha'))}: {title})으로 업데이트하시겠습니까?\n{mode_note}"
            )
            self.confirm_frame.show()
            self.btn_apply.setEnabled(False)

        def _cancel_apply_confirmation(self):
            self.confirm_frame.hide()
            if self._last_check and self._last_check.get("update_available") and not self._busy:
                self.btn_apply.setEnabled(True)

        def start_apply(self):
            if self._busy:
                return
            self._set_busy(True, applying=True)
            self.result_frame.hide()
            self.btn_restart.hide()
            self.lbl_status.setText("업데이트를 다운로드 및 적용하는 중입니다... 잠시만 기다려 주세요.")

            snapshot_check = dict(self._last_check) if isinstance(self._last_check, dict) else None

            def worker():
                try:
                    res = self.updater.apply(check_info=snapshot_check)
                except Exception as exc:
                    res = {"ok": False, "updated": False, "error": str(exc), "message": str(exc)}
                try:
                    self.apply_finished_signal.emit(res)
                except RuntimeError:
                    pass

            threading.Thread(target=worker, daemon=False).start()

        def _on_apply_finished(self, result: Dict[str, Any]):
            self._last_apply = result
            self._set_busy(False, applying=False)
            self.result_frame.show()
            if result.get("ok"):
                self.result_frame.setStyleSheet(
                    "QFrame { background-color: #10202e; border: 1px solid #22c55e; border-radius: 10px; }"
                )
                self.lbl_status.setText("업데이트가 완료되었습니다." if result.get("updated") else "이미 최신 버전입니다.")
                self.lbl_result.setText(format_apply_summary(result))
                self.btn_apply.setEnabled(False)
                if result.get("restart_recommended"):
                    self.btn_restart.show()
            else:
                self.result_frame.setStyleSheet(
                    "QFrame { background-color: #26161c; border: 1px solid #ef4444; border-radius: 10px; }"
                )
                self.lbl_status.setText("업데이트를 적용하지 못했습니다.")
                self.lbl_result.setText(format_apply_summary(result))
                if self._last_check and self._last_check.get("update_available"):
                    self.btn_apply.setEnabled(True)

        def _handle_restart(self):
            if callable(self.on_restart):
                self.accept()
                self.on_restart()
            else:
                self.accept()
                relaunch_application(root_dir=self.updater.root_dir)


def main(argv: Optional[List[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="WF-Companion GitHub main auto-updater")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="Check if a newer commit is available on GitHub main")
    group.add_argument("--apply", action="store_true", help="Apply the latest update safely")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--owner", default=DEFAULT_OWNER, help="GitHub repository owner")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="GitHub repository name")
    parser.add_argument("--branch", default=DEFAULT_BRANCH, help="GitHub branch name")
    parser.add_argument("--root", default=None, help="Target installation directory (defaults to project root)")
    args = parser.parse_args(argv)

    updater = AppUpdater(root_dir=args.root, owner=args.owner, repo=args.repo, branch=args.branch)
    if args.apply:
        result = updater.apply()
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(format_apply_summary(result))
        return 0 if result.get("ok") else 1

    info = updater.check()
    if args.json:
        print(json.dumps(info, ensure_ascii=False, indent=2))
    else:
        print(format_check_summary(info))
    return 0 if info.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
