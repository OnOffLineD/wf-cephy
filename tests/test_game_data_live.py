"""/데이터 갱신 output lives in a git-ignored folder; the tracked data/ copies are only the bundled baseline."""
import json
import os
import shutil
import subprocess

import pytest

from scripts.app_updater import AppUpdater
from scripts.drop_lookup import DropIndex
from scripts.game_catalog import GameCatalog
from scripts.path_config import REFRESHED_GAME_DATA_FILES, game_data_file, get_path, live_game_data_dir
from scripts.update_game_data import ENGINE_FILES, GameDataUpdater
from scripts.wf_data_indexer import WFDataIndexer
from tests.test_app_updater import SHA_NEW, SHA_OLD, _cp
from tests.test_game_data import FakeServer, fake_item


@pytest.fixture
def user_dir(tmp_path, monkeypatch):
    """A private WF_USER_DATA_DIR, so live files written here never leak into other tests."""
    path = tmp_path / "user"
    path.mkdir()
    monkeypatch.setenv("WF_USER_DATA_DIR", str(path))
    return path


def _write_live(rel, data):
    path = live_game_data_dir(*rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return path


# ------------------------------------------------------------------ lookup

def test_refreshed_copy_wins_per_file_and_only_for_refreshed_files(user_dir, tmp_path):
    bundled = get_path("data", "raw_wfcd", "Melee.json")
    assert game_data_file(bundled) == bundled
    live = _write_live("raw_wfcd/Melee.json", [])
    assert game_data_file(bundled) == live
    # A file without its own refresh still reads the bundled copy.
    assert game_data_file(get_path("data", "raw_wfcd", "Primary.json")) == get_path("data", "raw_wfcd", "Primary.json")
    # Curated files and other folders are never redirected.
    _write_live("raw_wfcd/weapon_arcanes.json", [])
    curated = get_path("data", "raw_wfcd", "weapon_arcanes.json")
    assert game_data_file(curated) == curated
    custom = str(tmp_path / "raw_wfcd" / "Melee.json")
    assert game_data_file(custom) == custom


def test_refresh_list_matches_what_the_updater_downloads():
    expected = {f"raw_wfcd/{n}" for n in ENGINE_FILES} | {"raw_wfcd/drops_all.json", "raw_wfcd/ko.json", "game_catalog.json"}
    assert set(REFRESHED_GAME_DATA_FILES) == expected


# ------------------------------------------------------------------ refresh

def test_default_refresh_writes_live_folder_and_leaves_bundled_baseline(user_dir, tmp_path, monkeypatch):
    bundled = tmp_path / "bundled"
    (bundled / "raw_wfcd").mkdir(parents=True)
    # The baseline already has item 0, so only 1 and 2 are new: "current" is read from the baseline.
    (bundled / "raw_wfcd" / "Primary.json").write_text(json.dumps([fake_item("Primary.json-0")]), encoding="utf-8")
    monkeypatch.setattr("scripts.update_game_data.get_path", lambda *parts: str(bundled.joinpath(*parts[1:])))
    before = (bundled / "raw_wfcd" / "Primary.json").read_bytes()

    report = GameDataUpdater(fetch=FakeServer(), state_path=str(tmp_path / "state.json")).update()

    assert "Primary.json-0" not in report["added"] and "Primary.json-1" in report["added"]
    for rel in REFRESHED_GAME_DATA_FILES:
        assert os.path.exists(live_game_data_dir(*rel.split("/"))), rel
    assert (bundled / "raw_wfcd" / "Primary.json").read_bytes() == before
    assert sorted(os.listdir(bundled / "raw_wfcd")) == ["Primary.json"]

    # A second refresh compares against the first one, no longer the baseline.
    report = GameDataUpdater(fetch=FakeServer(), state_path=str(tmp_path / "state.json")).update()
    assert report["added"] == []


# ------------------------------------------------------------------ readers

def test_readers_use_the_refreshed_copy(user_dir):
    _write_live("game_catalog.json", {"entries": [{"kind": "resource", "ko": "라이브 전용 자원", "en": "Live Only Resource"}]})
    assert [e["en"] for e in GameCatalog().entries] == ["Live Only Resource"]

    _write_live("raw_wfcd/drops_all.json", {"marker": "live"})
    assert DropIndex()._read("drops_all.json") == {"marker": "live"}

    with open(get_path("data", "raw_wfcd", "Melee.json"), encoding="utf-8") as f:
        bundled_melee = json.load(f)
    blade = dict(bundled_melee[0], name="Live Test Blade", uniqueName="/Live/TestBlade")
    _write_live("raw_wfcd/Melee.json", [blade])
    index = WFDataIndexer().weapons_index
    assert "live test blade" in index
    assert bundled_melee[0]["name"].lower() not in index


# ------------------------------------------------------------------ app update migration

def _migration_git(tmp_path, incoming, calls):
    head = {"sha": SHA_OLD}

    def fake_git(args, cwd, timeout):
        calls.append(args)
        if args == ["rev-parse", "HEAD"]:
            return _cp(0, stdout=head["sha"] + "\n")
        if args == ["status", "--porcelain"]:
            return _cp(0, stdout=" M data/game_catalog.json\n M data/raw_wfcd/Melee.json\n M notes.txt\n")
        if args == ["rev-parse", "--abbrev-ref", "HEAD"]:
            return _cp(0, stdout="main\n")
        if args == ["fetch", "origin", "main"]:
            return _cp(0)
        if args[:2] == ["checkout", "--"]:
            return _cp(0)
        if args[:2] == ["diff", "--name-only"]:
            return _cp(0, stdout="\n".join(incoming) + "\n")
        if args == ["merge", "--ff-only", "origin/main"]:
            head["sha"] = SHA_NEW
            return _cp(0, stdout="Fast-forward\n")
        raise AssertionError(f"Unexpected git args: {args}")

    return fake_git


def test_update_moves_in_place_refresh_to_live_folder_instead_of_blocking(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "data" / "raw_wfcd").mkdir(parents=True)
    (tmp_path / "data" / "game_catalog.json").write_text('{"v": "refreshed"}', encoding="utf-8")
    (tmp_path / "data" / "raw_wfcd" / "Melee.json").write_text('["refreshed"]', encoding="utf-8")
    live = tmp_path / "data" / "game_data_live"
    (live / "raw_wfcd").mkdir(parents=True)
    (live / "raw_wfcd" / "Melee.json").write_text('["newer refresh"]', encoding="utf-8")
    calls = []
    # The update ships a new baseline catalog: before, that overlap stopped the update.
    fake_git = _migration_git(tmp_path, ["data/game_catalog.json", "scripts/app.py"], calls)

    res = AppUpdater(root_dir=str(tmp_path), git_runner=fake_git).apply()

    assert res["ok"] is True and res["updated"] is True
    assert ["checkout", "--", "data/game_catalog.json", "data/raw_wfcd/Melee.json"] in calls
    assert res["moved_game_data"] == ["data/game_catalog.json", "data/raw_wfcd/Melee.json"]
    assert res["dirty_files"] == ["data/game_catalog.json", "data/raw_wfcd/Melee.json", "notes.txt"]
    assert "게임 데이터 2개" in res["message"] and "로컬 변경 1개" in res["message"]
    assert (live / "game_catalog.json").read_text(encoding="utf-8") == '{"v": "refreshed"}'
    # A newer refresh already in the live folder is not replaced by the stale in-place one.
    assert (live / "raw_wfcd" / "Melee.json").read_text(encoding="utf-8") == '["newer refresh"]'


def test_failed_restore_leaves_files_to_the_overlap_check(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "game_catalog.json").write_text("{}", encoding="utf-8")
    calls = []
    fake_git = _migration_git(tmp_path, ["data/game_catalog.json"], calls)

    def checkout_fails(args, cwd, timeout):
        return _cp(1, stderr="error: pathspec") if args[:2] == ["checkout", "--"] else fake_git(args, cwd, timeout)

    res = AppUpdater(root_dir=str(tmp_path), git_runner=checkout_fails).apply()
    assert res["error_kind"] == "dirty_worktree"
    assert res["conflicting_files"] == ["data/game_catalog.json"]
    assert ["merge", "--ff-only", "origin/main"] not in calls


@pytest.mark.skipif(shutil.which("git") is None, reason="git executable not installed")
def test_real_git_update_over_in_place_refresh(tmp_path):
    def run(args, cwd):
        return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True,
                              encoding="utf-8", check=True).stdout.strip()

    bare, seed, client = tmp_path / "origin.git", tmp_path / "seed", tmp_path / "client"
    bare.mkdir()
    run(["init", "--bare"], bare)
    run(["clone", str(bare), str(seed)], tmp_path)
    for repo in (seed,):
        run(["config", "user.email", "t@example.com"], repo)
        run(["config", "user.name", "T"], repo)
    run(["checkout", "-b", "main"], seed)
    (seed / "data").mkdir()
    (seed / "data" / "game_catalog.json").write_text('{"v": 1}\n', encoding="utf-8")
    (seed / "app.py").write_text("VERSION = 1\n", encoding="utf-8")
    run(["add", "."], seed)
    run(["commit", "-m", "initial"], seed)
    run(["push", "-u", "origin", "main"], seed)
    run(["symbolic-ref", "HEAD", "refs/heads/main"], bare)
    run(["clone", "-b", "main", str(bare), str(client)], tmp_path)

    # An older version refreshed the data in place; then upstream ships a new baseline and code.
    (client / "data" / "game_catalog.json").write_text('{"v": "refreshed"}\n', encoding="utf-8")
    (seed / "data" / "game_catalog.json").write_text('{"v": 2}\n', encoding="utf-8")
    (seed / "app.py").write_text("VERSION = 2\n", encoding="utf-8")
    run(["commit", "-am", "v2"], seed)
    run(["push", "origin", "main"], seed)

    res = AppUpdater(root_dir=str(client), branch="main").apply()

    assert res["ok"] is True and res["updated"] is True, res
    assert (client / "app.py").read_text(encoding="utf-8") == "VERSION = 2\n"
    assert (client / "data" / "game_catalog.json").read_text(encoding="utf-8") == '{"v": 2}\n'
    assert (client / "data" / "game_data_live" / "game_catalog.json").read_text(encoding="utf-8") == '{"v": "refreshed"}\n'
    assert run(["status", "--porcelain", "--untracked-files=no"], client) == ""
