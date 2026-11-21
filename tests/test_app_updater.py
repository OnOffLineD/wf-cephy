import io
import json
import os
import shutil
import subprocess
import zipfile
from unittest.mock import MagicMock, patch

import pytest
import requests

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from scripts import app_updater as au
from scripts.app_updater import (
    AppUpdater,
    USER_AGENT,
    build_relaunch_command,
    format_apply_summary,
    format_check_summary,
    is_protected_path,
    relaunch_application,
    requirements_install_command,
)

SHA_OLD = "1111111111111111111111111111111111111111"
SHA_NEW = "2222222222222222222222222222222222222222"


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, content=b"", headers=None, bad_json=False):
        self.status_code = status_code
        self._json_data = json_data
        self._bad_json = bad_json
        self.headers = headers or {}
        if content:
            self.content = content
        elif json_data is not None:
            self.content = json.dumps(json_data, ensure_ascii=False).encode("utf-8")
        else:
            self.content = b""

    def json(self):
        if self._bad_json:
            raise ValueError("invalid json")
        return self._json_data


def _commit_payload(sha=SHA_NEW, message="feat: add updater\n\ndetails", date="2026-11-19T12:00:00Z", author="Tenno"):
    return {
        "sha": sha,
        "html_url": f"https://github.com/OnOffLineD/wf-cephy/commit/{sha}",
        "commit": {
            "message": message,
            "author": {"name": author, "date": date},
            "committer": {"name": author, "date": date},
        },
    }


def _make_zip_bytes(entries, prefix="wf-cephy-main/"):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        if prefix:
            zf.writestr(prefix, "")
        for name, data in entries.items():
            payload = data.encode("utf-8") if isinstance(data, str) else data
            zf.writestr(f"{prefix}{name}", payload)
    return buf.getvalue()


def _cp(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(args=["git"], returncode=returncode, stdout=stdout, stderr=stderr)


# ----------------------------------------------------------------------
# 1. Update Check Tests
# ----------------------------------------------------------------------
def test_check_up_to_date_git_mode(tmp_path):
    (tmp_path / ".git").mkdir()
    calls = []

    def fake_http(url, headers=None, timeout=None):
        calls.append((url, headers, timeout))
        return FakeResponse(200, _commit_payload(sha=SHA_OLD, message="chore: latest"))

    def fake_git(args, cwd, timeout):
        if args == ["rev-parse", "HEAD"]:
            return _cp(0, stdout=SHA_OLD + "\n")
        raise AssertionError(f"Unexpected git command: {args}")

    updater = AppUpdater(root_dir=str(tmp_path), http_get=fake_http, git_runner=fake_git, timeout=11)
    info = updater.check()

    assert info["ok"] is True
    assert info["mode"] == "git"
    assert info["update_available"] is False
    assert info["local_sha"] == SHA_OLD
    assert info["remote_sha"] == SHA_OLD
    assert info["behind_count"] == 0
    assert info["commit_title"] == "chore: latest"
    # Up-to-date check must make only 1 API request with User-Agent and timeout.
    assert len(calls) == 1
    assert calls[0][0].endswith("/repos/OnOffLineD/wf-cephy/commits/main")
    assert calls[0][1]["User-Agent"] == USER_AGENT
    assert calls[0][2] == 11
    assert "최신 버전" in format_check_summary(info)


def test_check_update_available_with_compare_behind_count(tmp_path):
    (tmp_path / ".git").mkdir()

    def fake_http(url, headers=None, timeout=None):
        if "/commits/" in url:
            return FakeResponse(200, _commit_payload(sha=SHA_NEW, message="fix: 한글 커밋 제목\n본문"))
        if "/compare/" in url:
            return FakeResponse(
                200,
                {
                    "status": "ahead",
                    "ahead_by": 4,
                    "behind_by": 0,
                    "html_url": "https://github.com/OnOffLineD/wf-cephy/compare/1111111...2222222",
                },
            )
        raise AssertionError(f"Unexpected URL: {url}")

    def fake_git(args, cwd, timeout):
        if args == ["rev-parse", "HEAD"]:
            return _cp(0, stdout=SHA_OLD + "\n")
        raise AssertionError(f"Unexpected git command: {args}")

    updater = AppUpdater(root_dir=str(tmp_path), http_get=fake_http, git_runner=fake_git)
    info = updater.check()

    assert info["ok"] is True
    assert info["update_available"] is True
    assert info["local_sha"] == SHA_OLD
    assert info["remote_sha"] == SHA_NEW
    assert info["behind_count"] == 4
    assert info["commit_title"] == "fix: 한글 커밋 제목"
    assert info["commit_date"] == "2026-11-19T12:00:00Z"
    assert "compare/1111111...2222222" in info["compare_url"]
    summary = format_check_summary(info)
    assert "4개 커밋 뒤처짐" in summary and "한글 커밋 제목" in summary


def test_check_local_ahead_of_remote_not_flagged_as_update(tmp_path):
    (tmp_path / ".git").mkdir()

    def fake_http(url, headers=None, timeout=None):
        if "/commits/" in url:
            return FakeResponse(200, _commit_payload(sha=SHA_OLD))
        if "/compare/" in url:
            return FakeResponse(200, {"status": "behind", "ahead_by": 0, "behind_by": 2})
        raise AssertionError(f"Unexpected URL: {url}")

    updater = AppUpdater(
        root_dir=str(tmp_path),
        http_get=fake_http,
        git_runner=lambda args, cwd, timeout: _cp(0, stdout=SHA_NEW + "\n"),
    )
    info = updater.check()

    assert info["ok"] is True
    assert info["update_available"] is False
    assert info["behind_count"] == 0
    assert info["ahead_count"] == 2


def test_check_archive_mode_state_detection(tmp_path):
    # No .git directory -> portable archive mode.
    def fake_http(url, headers=None, timeout=None):
        return FakeResponse(200, _commit_payload(sha=SHA_NEW))

    updater = AppUpdater(root_dir=str(tmp_path), http_get=fake_http)
    info_initial = updater.check()
    assert info_initial["ok"] is True
    assert info_initial["mode"] == "archive"
    assert info_initial["local_sha"] is None
    assert info_initial["update_available"] is True

    # Persist installed SHA and re-check -> up to date.
    state_file = tmp_path / "data" / "app_update_state.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps({"installed_sha": SHA_NEW}), encoding="utf-8")

    info_after = updater.check()
    assert info_after["ok"] is True
    assert info_after["local_sha"] == SHA_NEW
    assert info_after["update_available"] is False
    assert info_after["behind_count"] == 0


@pytest.mark.parametrize(
    "behavior, expected_kind",
    [
        (requests.ConnectionError("offline"), "offline"),
        (requests.Timeout("timed out"), "timeout"),
        (FakeResponse(403, {"message": "API rate limit exceeded"}, headers={"X-RateLimit-Remaining": "0"}), "rate_limit"),
        (FakeResponse(429, {"message": "too many requests"}), "rate_limit"),
        (FakeResponse(404, {"message": "Not Found"}), "not_found"),
        (FakeResponse(500, {"message": "Internal Error"}), "http_error"),
        (FakeResponse(200, bad_json=True), "invalid_response"),
    ],
)
def test_check_handles_network_and_http_errors_gracefully(tmp_path, behavior, expected_kind):
    def fake_http(url, headers=None, timeout=None):
        if isinstance(behavior, Exception):
            raise behavior
        return behavior

    updater = AppUpdater(root_dir=str(tmp_path), http_get=fake_http)
    info = updater.check()

    assert info["ok"] is False
    assert info["update_available"] is False
    assert info["error_kind"] == expected_kind
    assert info["error"]
    assert "실패" in format_check_summary(info)


# ----------------------------------------------------------------------
# 2. Git Mode Apply Tests
# ----------------------------------------------------------------------
def test_git_apply_clean_fast_forward_and_requirements_changed(tmp_path):
    (tmp_path / ".git").mkdir()
    head_state = {"sha": SHA_OLD}
    git_calls = []

    def fake_git(args, cwd, timeout):
        git_calls.append(args)
        if args == ["rev-parse", "HEAD"]:
            return _cp(0, stdout=head_state["sha"] + "\n")
        if args == ["status", "--porcelain"]:
            return _cp(0, stdout="")
        if args == ["rev-parse", "--abbrev-ref", "HEAD"]:
            return _cp(0, stdout="main\n")
        if args == ["fetch", "origin", "main"]:
            return _cp(0, stdout="")
        if args == ["merge", "--ff-only", "origin/main"]:
            head_state["sha"] = SHA_NEW
            return _cp(0, stdout="Fast-forward\n")
        if args == ["diff", "--name-only", SHA_OLD, SHA_NEW]:
            return _cp(0, stdout="scripts/app_updater.py\nrequirements.txt\n")
        raise AssertionError(f"Unexpected git args: {args}")

    updater = AppUpdater(root_dir=str(tmp_path), git_runner=fake_git)
    res = updater.apply()

    assert res["ok"] is True
    assert res["updated"] is True
    assert res["mode"] == "git"
    assert res["previous_sha"] == SHA_OLD
    assert res["new_sha"] == SHA_NEW
    assert res["updated_files"] == ["scripts/app_updater.py", "requirements.txt"]
    assert res["requirements_changed"] is True
    assert res["restart_recommended"] is True
    assert ["fetch", "origin", "main"] in git_calls
    assert ["merge", "--ff-only", "origin/main"] in git_calls
    summary = format_apply_summary(res)
    assert "requirements.txt" in summary and "재시작" in summary


INCOMING_DIFF = ["diff", "--name-only", "--no-renames", "HEAD", "origin/main"]


def _dirty_git(status_out, incoming=None, merged=None, diff_fails=False):
    """Fake git for a dirty tree: `incoming` is what the update rewrites, `merged` collects merge calls."""
    calls = []
    head = {"sha": SHA_OLD}

    def fake_git(args, cwd, timeout):
        calls.append(args)
        if args == ["rev-parse", "HEAD"]:
            return _cp(0, stdout=head["sha"] + "\n")
        if args == ["status", "--porcelain"]:
            return _cp(0, stdout=status_out)
        if args == ["rev-parse", "--abbrev-ref", "HEAD"]:
            return _cp(0, stdout="main\n")
        if args == ["fetch", "origin", "main"]:
            return _cp(0)
        if args == INCOMING_DIFF:
            return _cp(128, stderr="fatal: bad revision") if diff_fails else _cp(0, stdout="\n".join(incoming or []) + "\n")
        if args == ["merge", "--ff-only", "origin/main"] and merged is not None:
            merged.append(args)
            head["sha"] = SHA_NEW
            return _cp(0, stdout="Fast-forward\n")
        if args == ["diff", "--name-only", SHA_OLD, SHA_NEW]:
            return _cp(0, stdout="\n".join(incoming or []) + "\n")
        raise AssertionError(f"Must not run {args} here!")

    return fake_git, calls


def test_git_apply_refuses_local_changes_to_files_the_update_rewrites(tmp_path):
    (tmp_path / ".git").mkdir()
    fake_git, git_calls = _dirty_git(" M scripts/desktop_companion.py\n?? temp_notes.txt\n",
                                     incoming=["scripts/desktop_companion.py", "README.md"])

    res = AppUpdater(root_dir=str(tmp_path), git_runner=fake_git).apply()

    assert res["ok"] is False
    assert res["updated"] is False
    assert res["error_kind"] == "dirty_worktree"
    assert "scripts/desktop_companion.py" in res["dirty_files"]
    assert "temp_notes.txt" in res["dirty_files"]
    # Only the overlapping file is named as the reason.
    assert res["conflicting_files"] == ["scripts/desktop_companion.py"]
    assert "scripts/desktop_companion.py" in res["error"] and "temp_notes.txt" not in res["error"]
    # Fetch only updates origin/main; nothing that changes the working tree ran.
    assert not any(c[0] in ("merge", "pull", "checkout", "reset", "stash") for c in git_calls)


def test_git_apply_keeps_unrelated_local_changes_and_updates_code(tmp_path):
    """A local edit the update doesn't touch must not stop a code update (git keeps it through the merge)."""
    (tmp_path / ".git").mkdir()
    merged = []
    fake_git, _ = _dirty_git(" M data/guide_aliases.json\n M rules/01_damage_formulas.md\n",
                             incoming=["scripts/llm_providers.py", "scripts/persona_dialog.py"], merged=merged)

    res = AppUpdater(root_dir=str(tmp_path), git_runner=fake_git).apply()

    assert res["ok"] is True and res["updated"] is True
    assert merged == [["merge", "--ff-only", "origin/main"]]
    assert res["dirty_files"] == ["data/guide_aliases.json", "rules/01_damage_formulas.md"]
    assert "로컬 변경 2개는 그대로 유지" in res["message"]


def test_git_apply_with_unknown_incoming_files_stays_conservative(tmp_path):
    (tmp_path / ".git").mkdir()
    fake_git, git_calls = _dirty_git(" M data/guide_aliases.json\n", diff_fails=True)

    res = AppUpdater(root_dir=str(tmp_path), git_runner=fake_git).apply()

    assert res["error_kind"] == "dirty_worktree"
    assert res["conflicting_files"] == ["data/guide_aliases.json"]
    assert ["merge", "--ff-only", "origin/main"] not in git_calls


@pytest.mark.parametrize("status_out, incoming", [
    ("R  old_name.py -> new_name.py\n", ["old_name.py"]),  # local rename of a file the update edits
    ("?? assets/new_icons/\n", ["assets/new_icons/send.png"]),  # untracked folder the update adds files into
    (' M "data/\\354\\235\\264\\353\\246\\204.json"\n', ['"data/\\354\\235\\264\\353\\246\\204.json"']),
])
def test_git_apply_overlap_covers_renames_folders_and_quoted_paths(tmp_path, status_out, incoming):
    (tmp_path / ".git").mkdir()
    fake_git, _ = _dirty_git(status_out, incoming=incoming)
    res = AppUpdater(root_dir=str(tmp_path), git_runner=fake_git).apply()
    assert res["error_kind"] == "dirty_worktree" and res["conflicting_files"]


def test_git_merge_refusing_to_overwrite_is_reported_as_local_changes(tmp_path):
    (tmp_path / ".git").mkdir()

    def fake_git(args, cwd, timeout):
        if args == ["rev-parse", "HEAD"]:
            return _cp(0, stdout=SHA_OLD + "\n")
        if args == ["status", "--porcelain"]:
            return _cp(0, stdout="")
        if args == ["rev-parse", "--abbrev-ref", "HEAD"]:
            return _cp(0, stdout="main\n")
        if args == ["fetch", "origin", "main"]:
            return _cp(0)
        if args == ["merge", "--ff-only", "origin/main"]:
            return _cp(1, stderr="error: Your local changes to the following files would be overwritten by merge:\n"
                                 "\tapp.py\nPlease commit your changes or stash them before you merge.\nAborting\n")
        raise AssertionError(f"Unexpected args: {args}")

    res = AppUpdater(root_dir=str(tmp_path), git_runner=fake_git).apply()
    assert res["ok"] is False
    assert res["error_kind"] == "dirty_worktree"
    assert res["conflicting_files"] == ["app.py"]


def test_git_apply_ignores_own_untracked_state_file(tmp_path):
    (tmp_path / ".git").mkdir()

    def fake_git(args, cwd, timeout):
        if args == ["rev-parse", "HEAD"]:
            return _cp(0, stdout=SHA_OLD + "\n")
        if args == ["status", "--porcelain"]:
            return _cp(0, stdout="?? data/app_update_state.json\n")
        if args == ["rev-parse", "--abbrev-ref", "HEAD"]:
            return _cp(0, stdout="main\n")
        if args == ["fetch", "origin", "main"]:
            return _cp(0)
        if args == ["merge", "--ff-only", "origin/main"]:
            return _cp(0, stdout="Already up to date.\n")
        raise AssertionError(f"Unexpected args: {args}")

    res = AppUpdater(root_dir=str(tmp_path), git_runner=fake_git).apply()
    assert res["ok"] is True
    assert res["updated"] is False


def test_git_apply_non_fast_forward_failure(tmp_path):
    (tmp_path / ".git").mkdir()

    def fake_git(args, cwd, timeout):
        if args == ["rev-parse", "HEAD"]:
            return _cp(0, stdout=SHA_OLD + "\n")
        if args == ["status", "--porcelain"]:
            return _cp(0, stdout="")
        if args == ["rev-parse", "--abbrev-ref", "HEAD"]:
            return _cp(0, stdout="main\n")
        if args == ["fetch", "origin", "main"]:
            return _cp(0)
        if args == ["merge", "--ff-only", "origin/main"]:
            return _cp(128, stderr="fatal: Not possible to fast-forward, aborting.\n")
        raise AssertionError(f"Unexpected args: {args}")

    res = AppUpdater(root_dir=str(tmp_path), git_runner=fake_git).apply()
    assert res["ok"] is False
    assert res["updated"] is False
    assert res["error_kind"] == "non_fast_forward"
    assert "Fast-Forward" in res["error"]


@pytest.mark.parametrize("branch_out, expected_kind", [("feature/work", "wrong_branch"), ("HEAD", "detached_head")])
def test_git_apply_refuses_wrong_branch_or_detached_head(tmp_path, branch_out, expected_kind):
    (tmp_path / ".git").mkdir()

    def fake_git(args, cwd, timeout):
        if args == ["rev-parse", "HEAD"]:
            return _cp(0, stdout=SHA_OLD + "\n")
        if args == ["status", "--porcelain"]:
            return _cp(0, stdout="")
        if args == ["rev-parse", "--abbrev-ref", "HEAD"]:
            return _cp(0, stdout=branch_out + "\n")
        raise AssertionError(f"Must not run {args}")

    res = AppUpdater(root_dir=str(tmp_path), git_runner=fake_git).apply()
    assert res["ok"] is False
    assert res["error_kind"] == expected_kind


@pytest.mark.skipif(shutil.which("git") is None, reason="git executable not installed")
def test_git_apply_end_to_end_in_isolated_temp_repo(tmp_path):
    """Exercises real git fetch + merge --ff-only strictly inside tmp_path (never real repo)."""
    def run(args, cwd):
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        return proc.stdout.strip()

    bare = tmp_path / "origin.git"
    bare.mkdir()
    run(["init", "--bare"], bare)

    seed = tmp_path / "seed"
    run(["clone", str(bare), str(seed)], tmp_path)
    run(["config", "user.email", "test@example.com"], seed)
    run(["config", "user.name", "Test"], seed)
    run(["checkout", "-b", "main"], seed)
    (seed / "app.py").write_text("VERSION = 1\n", encoding="utf-8")
    (seed / "requirements.txt").write_text("requests>=2.31.0\n", encoding="utf-8")
    (seed / "game_catalog.json").write_text('{"v": 1}\n', encoding="utf-8")
    run(["add", "."], seed)
    run(["commit", "-m", "initial"], seed)
    run(["push", "-u", "origin", "main"], seed)
    run(["symbolic-ref", "HEAD", "refs/heads/main"], bare)

    client = tmp_path / "client"
    run(["clone", "-b", "main", str(bare), str(client)], tmp_path)
    run(["config", "user.email", "test@example.com"], client)
    run(["config", "user.name", "Test"], client)

    # Upstream gets a new commit.
    (seed / "app.py").write_text("VERSION = 2\n", encoding="utf-8")
    run(["add", "app.py"], seed)
    run(["commit", "-m", "v2"], seed)
    run(["push", "origin", "main"], seed)
    upstream_sha = run(["rev-parse", "HEAD"], seed)

    # 1. Dirty local file -> must refuse and preserve local edit.
    (client / "app.py").write_text("LOCAL_DIRTY\n", encoding="utf-8")
    updater = AppUpdater(root_dir=str(client), branch="main")
    dirty_res = updater.apply()
    assert dirty_res["ok"] is False
    assert dirty_res["error_kind"] == "dirty_worktree"
    assert (client / "app.py").read_text(encoding="utf-8") == "LOCAL_DIRTY\n"

    # 2. Only a file the update doesn't touch is changed (like /데이터 갱신 output) -> fast-forwards and keeps it.
    (client / "app.py").write_text("VERSION = 1\n", encoding="utf-8")
    (client / "game_catalog.json").write_text('{"v": "refreshed"}\n', encoding="utf-8")
    ok_res = updater.apply()
    assert ok_res["ok"] is True
    assert ok_res["updated"] is True
    assert ok_res["new_sha"] == upstream_sha
    assert ok_res["updated_files"] == ["app.py"]
    assert ok_res["requirements_changed"] is False
    assert (client / "app.py").read_text(encoding="utf-8") == "VERSION = 2\n"
    assert (client / "game_catalog.json").read_text(encoding="utf-8") == '{"v": "refreshed"}\n'


# ----------------------------------------------------------------------
# 3. Archive / Portable Mode Tests
# ----------------------------------------------------------------------
def test_is_protected_path_covers_all_user_and_runtime_paths():
    protected = [
        "data/user_builds.json",
        "data/user_checklist.json",
        "data/user_checklist.json.meta.json",
        "data/persona_config.json",
        "data/wf_database.sqlite",
        "data/wf_database.sqlite-wal",
        "data/chroma_db/index.bin",
        "data/wiki_cache/page.json",
        "data/raw_wfcd/Primary.json",
        "data/logs/app-errors.log",
        "data/app_update_state.json",
        "data/game_data_state.json",
        ".env",
        ".env.local",
        "python_embed/python.exe",
        "models/google_gemma.gguf",
        "graphify-out/graph.json",
        ".git/HEAD",
        "bin/llama-server.exe",
    ]
    for path in protected:
        assert is_protected_path(path) is True, f"Expected protected: {path}"

    allowed = [
        "main_companion.py",
        "requirements.txt",
        "scripts/app_updater.py",
        "scripts/desktop_companion.py",
        "rules/wiki_docs/boss.md",
        "data/arcane_effects.json",
        "assets/icons/refresh.png",
    ]
    for path in allowed:
        assert is_protected_path(path) is False, f"Expected updatable: {path}"


def test_archive_apply_extracts_preserves_protected_files_and_persists_state(tmp_path):
    # Pre-existing app files.
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "demo.py").write_text("OLD = 1\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("requests>=2.31.0\n", encoding="utf-8")

    # Pre-existing protected user & runtime files that MUST remain untouched.
    protected_sentinels = {
        "data/user_builds.json": '{"builds": ["my_torid"]}',
        "data/user_checklist.json": '{"items": ["sortie"]}',
        "data/persona_config.json": '{"mode": "custom", "prompt": "나만의 오디스"}',
        "data/wf_database.sqlite": "SQLITE-SENTINEL",
        "data/chroma_db/store.bin": "CHROMA-SENTINEL",
        "data/wiki_cache/cached.json": '{"cached": true}',
        "data/raw_wfcd/Primary.json": '[{"name": "Braton"}]',
        "data/logs/app-errors.log": "existing log line",
        ".env": "SECRET_KEY=keep_me",
        "python_embed/python.exe": "EMBED-PY",
        "models/model.gguf": "GGUF-WEIGHTS",
        "graphify-out/graph.json": '{"nodes": 1}',
    }
    for rel, content in protected_sentinels.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    # Incoming archive includes updated app files AND attempts to overwrite every protected path.
    zip_entries = {
        "scripts/demo.py": "NEW = 2  # 한글\n",
        "scripts/new_helper.py": "def hi(): return 'ok'\n",
        "requirements.txt": "requests>=2.32.0\n",
        **{rel: "OVERWRITTEN_BAD" for rel in protected_sentinels},
        "data/app_update_state.json": '{"installed_sha": "0000000"}',
    }
    zip_bytes = _make_zip_bytes(zip_entries)

    def fake_http(url, headers=None, timeout=None):
        if "/commits/" in url:
            return FakeResponse(200, _commit_payload(sha=SHA_NEW, message="feat: archive release"))
        if url.endswith("/archive/refs/heads/main.zip"):
            return FakeResponse(200, content=zip_bytes)
        raise AssertionError(f"Unexpected URL: {url}")

    updater = AppUpdater(root_dir=str(tmp_path), http_get=fake_http)
    res = updater.apply()

    assert res["ok"] is True
    assert res["updated"] is True
    assert res["mode"] == "archive"
    assert res["new_sha"] == SHA_NEW
    assert res["requirements_changed"] is True
    assert res["rolled_back"] is False
    assert set(res["updated_files"]) == {"scripts/demo.py", "scripts/new_helper.py", "requirements.txt"}

    # Updated files written with UTF-8.
    assert (tmp_path / "scripts" / "demo.py").read_text(encoding="utf-8") == "NEW = 2  # 한글\n"
    assert (tmp_path / "scripts" / "new_helper.py").read_text(encoding="utf-8") == "def hi(): return 'ok'\n"
    assert (tmp_path / "requirements.txt").read_text(encoding="utf-8") == "requests>=2.32.0\n"

    # Every protected user/runtime file stayed byte-for-byte identical.
    for rel, sentinel in protected_sentinels.items():
        assert (tmp_path / rel).read_text(encoding="utf-8") == sentinel, f"Protected file clobbered: {rel}"

    # State file persisted with new SHA.
    state = json.loads((tmp_path / "data" / "app_update_state.json").read_text(encoding="utf-8"))
    assert state["installed_sha"] == SHA_NEW
    assert state["mode"] == "archive"
    assert state["branch"] == "main"


def test_archive_apply_rolls_back_all_changes_on_write_error(tmp_path, monkeypatch):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "a.py").write_text("OLD_A", encoding="utf-8")
    (tmp_path / "scripts" / "b.py").write_text("OLD_B", encoding="utf-8")
    (tmp_path / "data").mkdir()
    state_file = tmp_path / "data" / "app_update_state.json"
    state_file.write_text(json.dumps({"installed_sha": SHA_OLD}), encoding="utf-8")

    zip_bytes = _make_zip_bytes(
        {
            "scripts/a.py": "NEW_A",
            "scripts/new_dir/created.py": "CREATED",
            "scripts/b.py": "NEW_B",
        }
    )

    def fake_http(url, headers=None, timeout=None):
        if "/commits/" in url:
            return FakeResponse(200, _commit_payload(sha=SHA_NEW))
        if "/compare/" in url:
            return FakeResponse(200, {"status": "ahead", "ahead_by": 1, "behind_by": 0})
        if url.endswith(".zip"):
            return FakeResponse(200, content=zip_bytes)
        raise AssertionError(url)

    real_write = au._write_bytes_atomic

    def failing_write(path, payload):
        if os.path.basename(path) == "b.py" and payload == b"NEW_B":
            raise OSError("simulated disk full")
        return real_write(path, payload)

    monkeypatch.setattr(au, "_write_bytes_atomic", failing_write)

    updater = AppUpdater(root_dir=str(tmp_path), http_get=fake_http)
    res = updater.apply()

    assert res["ok"] is False
    assert res["updated"] is False
    assert res["rolled_back"] is True
    assert "simulated disk full" in res["error"]

    # Overwritten file restored, newly created file & directory deleted, state untouched.
    assert (tmp_path / "scripts" / "a.py").read_text(encoding="utf-8") == "OLD_A"
    assert (tmp_path / "scripts" / "b.py").read_text(encoding="utf-8") == "OLD_B"
    assert not (tmp_path / "scripts" / "new_dir" / "created.py").exists()
    assert not (tmp_path / "scripts" / "new_dir").exists()
    assert json.loads(state_file.read_text(encoding="utf-8"))["installed_sha"] == SHA_OLD


@pytest.mark.parametrize(
    "bad_zip",
    [
        b"not a zip archive at all",
        _make_zip_bytes({"../../escape.py": "bad"}, prefix="wf-cephy-main/"),
        _make_zip_bytes({"/abs_evil.py": "bad"}, prefix=""),
    ],
)
def test_archive_apply_rejects_corrupt_or_traversal_zip(tmp_path, bad_zip):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "keep.py").write_text("KEEP", encoding="utf-8")

    def fake_http(url, headers=None, timeout=None):
        if "/commits/" in url:
            return FakeResponse(200, _commit_payload(sha=SHA_NEW))
        if url.endswith(".zip"):
            return FakeResponse(200, content=bad_zip)
        raise AssertionError(url)

    res = AppUpdater(root_dir=str(tmp_path), http_get=fake_http).apply()
    assert res["ok"] is False
    assert res["error_kind"] == "invalid_archive"
    assert (tmp_path / "scripts" / "keep.py").read_text(encoding="utf-8") == "KEEP"
    assert not (tmp_path / "data" / "app_update_state.json").exists()


# ----------------------------------------------------------------------
# 4. Post-Update Helpers & CLI Tests
# ----------------------------------------------------------------------
def test_relaunch_and_requirements_helpers(tmp_path):
    (tmp_path / "main_companion.py").write_text("", encoding="utf-8")
    req_cmd = requirements_install_command(python_executable="py.exe", root_dir=str(tmp_path))
    assert req_cmd == ["py.exe", "-m", "pip", "install", "-r", str(tmp_path / "requirements.txt")]

    cmd = build_relaunch_command(
        root_dir=str(tmp_path),
        argv=["--disable-llm", "--unrelated"],
        python_executable="pyw.exe",
    )
    assert cmd == ["pyw.exe", str(tmp_path / "main_companion.py"), "--disable-llm"]

    events = []
    ok = relaunch_application(
        root_dir=str(tmp_path),
        argv=["--enable-llm"],
        python_executable="pyw.exe",
        before_exit=lambda: events.append("stop_llm"),
        spawner=lambda c, **kw: events.append(("spawn", c, kw["cwd"])),
        exit_func=lambda: events.append("quit"),
    )
    assert ok is True
    assert events[0] == "stop_llm"
    assert events[1][0] == "spawn" and events[1][1][-1] == "--enable-llm"
    assert events[2] == "quit"


def test_cli_check_and_apply(capsys):
    fake = MagicMock()
    fake.check.return_value = {
        "ok": True,
        "update_available": True,
        "local_sha": SHA_OLD,
        "remote_sha": SHA_NEW,
        "commit_title": "feat: cli test",
        "commit_message": "feat: cli test",
        "commit_date": "2026-11-19T12:00:00Z",
        "behind_count": 1,
        "compare_url": "https://github.com/OnOffLineD/wf-cephy/compare/1111111...2222222",
        "mode": "git",
        "branch": "main",
        "repo": "OnOffLineD/wf-cephy",
    }
    fake.apply.return_value = {"ok": False, "updated": False, "error": "dirty tree", "rolled_back": False}

    with patch("scripts.app_updater.AppUpdater", return_value=fake):
        code_check = au.main(["--check", "--json"])
        out_check = json.loads(capsys.readouterr().out)
        assert code_check == 0
        assert out_check["update_available"] is True

        code_apply = au.main(["--apply"])
        out_apply = capsys.readouterr().out
        assert code_apply == 1
        assert "dirty tree" in out_apply


# ----------------------------------------------------------------------
# 5. Headless Qt UI Smoke Tests
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def qapp():
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _drain(qapp, condition):
    try:
        from PyQt6.QtCore import QThread
    except ImportError:
        from PySide6.QtCore import QThread
    for _ in range(200):
        qapp.processEvents()
        if condition():
            return
        QThread.msleep(10)


def test_app_update_dialog_frameless_flow_check_confirm_apply_restart(qapp):
    try:
        from PyQt6.QtCore import Qt
    except ImportError:
        from PySide6.QtCore import Qt
    from scripts.app_updater import AppUpdateDialog
    from scripts.frameless_dialog import FramelessDialog

    fake_updater = MagicMock()
    fake_updater.root_dir = "."
    fake_updater.check.return_value = {
        "ok": True,
        "update_available": True,
        "local_sha": SHA_OLD,
        "remote_sha": SHA_NEW,
        "commit_title": "feat: UI smoke test",
        "commit_message": "feat: UI smoke test",
        "commit_date": "2026-11-19T12:00:00Z",
        "commit_author": "Tenno",
        "behind_count": 2,
        "compare_url": "https://github.com/OnOffLineD/wf-cephy/compare/1111111...2222222",
        "mode": "archive",
        "branch": "main",
        "repo": "OnOffLineD/wf-cephy",
    }
    fake_updater.apply.return_value = {
        "ok": True,
        "updated": True,
        "mode": "archive",
        "previous_sha": SHA_OLD,
        "new_sha": SHA_NEW,
        "updated_files": ["scripts/app_updater.py", "requirements.txt"],
        "requirements_changed": True,
        "rolled_back": False,
        "restart_recommended": True,
        "message": "업데이트 완료",
    }
    restarted = []
    dlg = AppUpdateDialog(updater=fake_updater, on_restart=lambda: restarted.append(True))
    try:
        assert isinstance(dlg, FramelessDialog)
        assert bool(dlg.windowFlags() & Qt.WindowType.FramelessWindowHint) is True

        _drain(qapp, lambda: dlg.btn_apply.isEnabled())
        assert dlg.btn_apply.isEnabled() is True
        assert "UI smoke test" in dlg.lbl_details.text()
        assert dlg.confirm_frame.isHidden() is True

        # Clicking Apply asks for explicit confirmation first (does not apply yet).
        dlg.btn_apply.click()
        assert dlg.confirm_frame.isHidden() is False
        fake_updater.apply.assert_not_called()

        # Confirming triggers non-blocking apply and exposes Restart button.
        dlg.btn_confirm_apply.click()
        _drain(qapp, lambda: not dlg.btn_restart.isHidden())
        fake_updater.apply.assert_called_once()
        assert not dlg.btn_restart.isHidden()
        assert "requirements.txt" in dlg.lbl_result.text()

        dlg.btn_restart.click()
        assert restarted == [True]
    finally:
        dlg.close()


def test_app_update_dialog_handles_offline_error(qapp):
    from scripts.app_updater import AppUpdateDialog

    fake_updater = MagicMock()
    fake_updater.check.return_value = {
        "ok": False,
        "update_available": False,
        "error": "네트워크 연결에 실패했습니다.",
        "error_kind": "offline",
    }
    dlg = AppUpdateDialog(updater=fake_updater)
    try:
        _drain(qapp, lambda: not dlg._busy)
        assert dlg.btn_apply.isEnabled() is False
        assert "네트워크 연결에 실패했습니다" in dlg.lbl_details.text()
    finally:
        dlg.close()


def test_desktop_companion_settings_button_and_startup_update_check(qapp, tmp_path, monkeypatch):
    try:
        from PyQt6.QtWidgets import QLabel, QPushButton
    except ImportError:
        from PySide6.QtWidgets import QLabel, QPushButton
    from scripts.desktop_companion import OrdisCompanionApp
    from scripts.persona_dialog import OrdisPersonaDialog
    from scripts.persona_manager import SettingsManager

    monkeypatch.setattr(OrdisCompanionApp, "refresh_world_events", lambda self: None)
    panel = OrdisCompanionApp()
    try:
        # 1. Settings dialog button hook attaches cleanly without modifying the 2 tabs.
        sm = SettingsManager(config_path=str(tmp_path / "settings.json"))
        settings_dlg = OrdisPersonaDialog(persona_manager=sm, parent=panel)
        try:
            btn = panel._attach_settings_update_button(settings_dlg)
            assert btn is not None
            assert settings_dlg.btn_app_update is btn
            assert "앱 업데이트" in btn.text()
            assert settings_dlg.tab_widget.count() == 2
        finally:
            settings_dlg.close()

        # 2. Startup background check notifies in chat with an action button when update exists.
        fake_updater = MagicMock()
        fake_updater.check.return_value = {
            "ok": True,
            "update_available": True,
            "local_sha": SHA_OLD,
            "remote_sha": SHA_NEW,
            "commit_title": "feat: shiny update",
            "commit_message": "feat: shiny update",
            "commit_date": "2026-11-19T12:00:00Z",
            "mode": "archive",
            "branch": "main",
            "repo": "OnOffLineD/wf-cephy",
        }
        before = panel.chat_list_layout.count()
        panel.check_app_update_in_background(updater=fake_updater)
        _drain(qapp, lambda: panel.chat_list_layout.count() > before)
        assert panel.chat_list_layout.count() > before
        bubble = panel.chat_list_layout.itemAt(panel.chat_list_layout.count() - 1).widget()
        assert any("새 업데이트" in lbl.text() for lbl in bubble.findChildren(QLabel))
        assert any("앱 업데이트 확인 및 적용" in b.text() for b in bubble.findChildren(QPushButton))

        # 3. Offline check emits no error bubble and does not crash.
        offline_updater = MagicMock()
        offline_updater.check.return_value = {"ok": False, "update_available": False, "error": "offline"}
        count_before_offline = panel.chat_list_layout.count()
        done_flag = []

        def offline_check():
            done_flag.append(True)
            return {"ok": False, "update_available": False, "error": "offline"}

        offline_updater.check.side_effect = offline_check
        panel.check_app_update_in_background(updater=offline_updater)
        _drain(qapp, lambda: bool(done_flag))
        qapp.processEvents()
        assert panel.chat_list_layout.count() == count_before_offline
    finally:
        panel.close()
