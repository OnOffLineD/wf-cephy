import json
import os
from datetime import datetime, timedelta, timezone

import pytest

from scripts.world_state_tracker import WorldStateTracker, cetus_estimate, format_remaining, parse_world_state

NOW = datetime(2026, 11, 4, 11, 26, tzinfo=timezone.utc)

# Shapes recorded from api.warframestat.us/pc on 2026-11-04.
RAW = {
    "cetusCycle": {"activation": "2026-11-04T10:50:00.000Z", "expiry": "2026-11-04T11:40:00.000Z", "isDay": False, "state": "night", "timeLeft": "14m 0s", "isCetus": True},
    "duviriCycle": {
        "activation": "2026-11-04T10:00:00.000Z", "expiry": "2026-11-04T12:00:00.000Z", "state": "joy",
        "choices": [
            {"category": "normal", "categoryKey": "EXC_NORMAL", "choices": ["Ivara", "Inaros", "Titania"]},
            {"category": "hard", "categoryKey": "EXC_HARD", "choices": ["Braton", "Lato", "Skana", "Paris", "Kunai"]},
        ],
    },
    "sortie": {"activation": "2026-11-04T00:00:00.000Z", "expiry": "2026-11-05T00:00:00.000Z", "boss": "Raptor", "faction": "Corpus", "factionKey": "Corpus", "missions": [], "variants": []},
    "archonHunt": {"activation": "2026-11-02T00:00:00.000Z", "expiry": "2026-11-09T00:00:00.000Z", "boss": "Archon Boreal", "faction": "Narmer", "factionKey": "Narmer", "missions": []},
    "voidTrader": {"activation": "2026-11-06T13:00:00.000Z", "expiry": "2026-11-08T13:00:00.000Z", "character": "Baro'Ki Teel", "location": "Kronia Relay (Saturn)", "inventory": [], "schedule": []},
}


def test_cetus_night_uses_is_day_field():
    ev = parse_world_state(RAW, NOW)
    assert ev["cetus"]["isNight"] is True
    assert "밤" in ev["cetus"]["state"]
    assert ev["cetus"]["timeLeft"] == "14분"
    assert ev["cetus"]["huntingTip"]


def test_sortie_and_archon_time_left_from_expiry():
    ev = parse_world_state(RAW, NOW)
    assert ev["sortie"]["timeLeft"] == "12시간 34분"
    assert ev["sortie"]["faction"] == "코퍼스"
    assert ev["archon"]["timeLeft"] == "4일 12시간"
    assert ev["archon"]["boss"] == "집정관 보리얼"


def test_void_trader_waiting_then_active():
    waiting = parse_world_state(RAW, NOW)["void_trader"]
    assert waiting["active"] is False
    assert waiting["status"] == "도착 전"
    assert waiting["eta"] == "2일 1시간"

    active = parse_world_state(RAW, datetime(2026, 11, 7, 13, 0, tzinfo=timezone.utc))["void_trader"]
    assert active["active"] is True
    assert active["status"] == "방문 중"
    assert active["eta"] == "1일"


def test_incarnon_rotation_comes_from_duviri_hard_choices():
    ev = parse_world_state(RAW, NOW)
    assert ev["incarnon"]["weapons"] == ["Braton", "Lato", "Skana", "Paris", "Kunai"]
    assert ev["duviri"]["state"] == "기쁨"
    assert ev["duviri"]["warframes"] == ["Ivara", "Inaros", "Titania"]


def test_names_are_translated_when_translator_given():
    ev = parse_world_state(RAW, NOW, translate=lambda name: {"Braton": "브래튼"}.get(name, name))
    assert ev["incarnon"]["weapons"][0] == "브래튼"


def test_missing_endpoints_show_unknown_not_fake_values():
    ev = parse_world_state({}, NOW)
    assert ev["sortie"]["boss"] == "확인 불가"
    assert ev["incarnon"]["weapons"] == []
    assert ev["cetus"]["estimated"] is True


def test_expired_cached_data_is_not_shown_as_current():
    ev = parse_world_state({"sortie": RAW["sortie"]}, NOW + timedelta(days=2))
    assert ev["sortie"]["timeLeft"] == "갱신 대기"


def test_cetus_estimate_follows_day_night_cycle():
    day_start = datetime(2026, 11, 4, 11, 40, tzinfo=timezone.utc)
    assert cetus_estimate(day_start + timedelta(minutes=10))["isNight"] is False
    assert cetus_estimate(day_start + timedelta(minutes=110))["isNight"] is True
    assert cetus_estimate(day_start - timedelta(minutes=10))["isNight"] is True


def test_format_remaining():
    assert format_remaining("2026-11-04T11:26:30.000Z", NOW) == "1분 미만"
    assert format_remaining("2026-11-04T12:30:00.000Z", NOW) == "1시간 4분"
    assert format_remaining("not-a-date", NOW) == ""


def test_format_world_events_has_no_placeholder_values():
    html = WorldStateTracker.format_world_events(parse_world_state(RAW, NOW))
    assert "N/A" not in html
    assert "밤" in html and "기쁨" in html and "Raptor" in html and "Braton" in html and "Kronia" in html


def test_format_world_events_escapes_markup():
    raw = dict(RAW, sortie=dict(RAW["sortie"], boss="<b>x</b>"))
    assert "<b>x</b>" not in WorldStateTracker.format_world_events(parse_world_state(raw, NOW))


def test_failed_endpoint_falls_back_to_last_good(tmp_path):
    tracker = WorldStateTracker(data_file=str(tmp_path / "c.json"))
    tracker._fetch_endpoint = lambda ep: RAW[ep]
    assert tracker.fetch_live_events()["sortie"]["boss"] == "Raptor"

    def fail(ep):
        raise TimeoutError(ep)

    tracker._fetch_endpoint = fail
    ev = tracker.fetch_live_events()
    assert ev["sortie"]["boss"] == "Raptor"
    assert "sortie" in ev["stale"]


@pytest.fixture
def tracker(tmp_path):
    t = WorldStateTracker(data_file=str(tmp_path / "c.json"))
    t.load_checklist()
    return t


@pytest.mark.parametrize("message", ["신스 디컨스트럭트 숙제로 추가해줘", "신스 디컨스트럭트 할 일에 등록해", "신스 디컨스트럭트 숙제 추가"])
def test_add_command_names_its_target(tracker, message):
    res = tracker.process_chat_todo_command(message)
    assert res["action"] == "ADD" and res["task"] == "신스 디컨스트럭트"
    assert "신스 디컨스트럭트" in [i["text"] for i in tracker.load_checklist()]


def test_add_command_without_target_uses_context_keyword(tracker):
    res = tracker.process_chat_todo_command("오늘 할 일로 추가해줘", context_keyword="신스 디컨스트럭트")
    assert res["action"] == "ADD" and res["task"] == "신스 디컨스트럭트"
    assert "신스 디컨스트럭트" in [i["text"] for i in tracker.load_checklist()]


def test_add_command_without_target_or_context_adds_nothing(tracker):
    before = tracker.load_checklist()
    assert tracker.process_chat_todo_command("오늘 할 일로 추가해줘") is None
    assert tracker.load_checklist() == before


@pytest.mark.parametrize("message", ["일일 완료", "오늘 다 했어", "방금 완료", "주간 완료"])
def test_vague_completion_marks_nothing(tracker, message):
    assert tracker.process_chat_todo_command(message) is None
    assert not any(i["done"] for i in tracker.load_checklist())


@pytest.mark.parametrize("message, item_id", [
    ("출격 완료", "daily_sortie"),
    ("오늘 집정관 끝냈어", "weekly_archon"),
    ("네트라셀 깼어", "weekly_netracell"),
    ("시마리스 다 했어", "daily_simaris"),
])
def test_named_completion_marks_that_item(tracker, message, item_id):
    assert tracker.process_chat_todo_command(message)["action"] == "COMPLETE"
    assert [i["id"] for i in tracker.load_checklist() if i["done"]] == [item_id]


def test_plain_delete_command_removes_item(tracker):
    assert tracker.process_chat_todo_command("집정관 삭제")["action"] == "DELETE"
    assert "weekly_archon" not in [i["id"] for i in tracker.load_checklist()]


def test_delete_of_unknown_item_changes_nothing(tracker):
    before = len(tracker.load_checklist())
    assert tracker.process_chat_todo_command("보라색 삭제") is None
    assert len(tracker.load_checklist()) == before


def test_custom_ids_stay_unique_after_delete(tracker):
    for text in ("A", "B", "C"):
        tracker.add_custom_item(text)
    first_custom = [i["id"] for i in tracker.load_checklist() if i["type"] == "custom"][0]
    tracker.delete_item(first_custom)
    tracker.add_custom_item("D")
    ids = [i["id"] for i in tracker.load_checklist()]
    assert len(ids) == len(set(ids))


def test_corrupt_file_is_kept_as_backup(tmp_path):
    path = tmp_path / "c.json"
    path.write_text('[{"id": "mine", "broken', encoding="utf-8")
    tracker = WorldStateTracker(data_file=str(path))
    items = tracker.load_checklist()
    assert items and items[0]["id"] == "daily_sortie"
    backups = [p for p in os.listdir(tmp_path) if ".corrupt" in p]
    assert len(backups) == 1
    assert "mine" in (tmp_path / backups[0]).read_text(encoding="utf-8")


def test_defaults_are_not_shared_between_loads(tmp_path):
    tracker = WorldStateTracker(data_file=str(tmp_path / "c.json"))
    tracker.toggle_item("daily_sortie")
    assert WorldStateTracker.DEFAULT_CHECKLIST[0]["done"] is False


def test_load_does_not_rewrite_unchanged_file(tracker):
    before = os.path.getmtime(tracker.data_file)
    os.utime(tracker.data_file, (before - 100, before - 100))
    tracker.load_checklist()
    assert os.path.getmtime(tracker.data_file) == before - 100


def test_daily_reset_keeps_weekly_done(tracker):
    tracker.toggle_item("daily_sortie")
    tracker.toggle_item("weekly_archon")
    meta_path = tracker.data_file + ".meta.json"
    meta = json.load(open(meta_path, encoding="utf-8"))
    meta["last_daily_key"] = "2000-01-01"
    json.dump(meta, open(meta_path, "w", encoding="utf-8"))
    done = {i["id"]: i["done"] for i in tracker.load_checklist()}
    assert done["daily_sortie"] is False
    assert done["weekly_archon"] is True


def test_old_integer_week_key_does_not_reset_same_week(tracker):
    tracker.toggle_item("weekly_archon")
    meta_path = tracker.data_file + ".meta.json"
    meta = json.load(open(meta_path, encoding="utf-8"))
    meta["last_weekly_key"] = datetime.now(timezone.utc).isocalendar()[1]
    json.dump(meta, open(meta_path, "w", encoding="utf-8"))
    assert {i["id"]: i["done"] for i in tracker.load_checklist()}["weekly_archon"] is True
