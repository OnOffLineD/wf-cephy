import json
import os

import pytest
from PIL import Image

from scripts.build_store import BuildStore, GRID_SLOTS, RIVEN_MOD, canonical_slot, slot_order
from scripts.screen_mod_analyzer import ScreenModAnalyzer

SAMPLE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ocrTestImg", "riven_reroll_nataruk.jpg")


@pytest.fixture(scope="module")
def shared_analyzer():
    return ScreenModAnalyzer()


@pytest.fixture
def analyzer(shared_analyzer, tmp_path):
    shared_analyzer.build_store = BuildStore(str(tmp_path / "builds.json"))
    shared_analyzer.clear_pending_riven()
    return shared_analyzer


def card(**stats):
    return {"name": "", "stats": stats, "unapplied": []}


def scan_result(analyzer, weapon, slots, panel=None):
    w_meta = analyzer.indexer.fuzzy_match_weapon(weapon)
    mods = []
    for slot, name in slots.items():
        base = {"name": RIVEN_MOD} if name == RIVEN_MOD else analyzer.indexer.mods_index[name.lower()]
        mods.append(dict(base, slot_name=slot, slot_index=slot_order(slot)))
    return {"w_meta": w_meta, "mod_objs": mods, "stats": panel or {}, "metrics": {}}


def test_store_saves_one_build_per_weapon(tmp_path):
    store = BuildStore(str(tmp_path / "b.json"))
    store.save_build({"weapon": "Torid", "slots": {"R1_C1": "Serration"}})
    store.save_build({"weapon": "Torid", "slots": {"R1_C1": "Hellfire"}})
    assert [b["slots"]["R1_C1"] for b in store.list_builds()] == ["Hellfire"]
    assert store.get_build("torid")["weapon"] == "Torid"
    assert "saved_at" in store.get_build("Torid")


def test_store_delete(tmp_path):
    store = BuildStore(str(tmp_path / "b.json"))
    store.save_build({"weapon": "Torid", "slots": {}})
    assert store.delete_build("Torid") is True
    assert store.delete_build("Torid") is False
    assert store.get_build("Torid") is None


def test_store_keeps_corrupt_file(tmp_path):
    path = tmp_path / "b.json"
    path.write_text('{"builds": {"mine', encoding="utf-8")
    store = BuildStore(str(path))
    assert store.list_builds() == []
    assert [p for p in os.listdir(tmp_path) if ".corrupt" in p]


def test_store_writes_utf8(tmp_path):
    path = tmp_path / "b.json"
    BuildStore(str(path)).save_build({"weapon": "Torid", "kr_name": "토리드", "slots": {}})
    assert "토리드" in path.read_text(encoding="utf-8")


def test_canonical_slots():
    assert canonical_slot("AuraStance") == "stance"
    assert canonical_slot("Exilus", {"type": "Stance Mod"}) == "stance"
    assert canonical_slot("Exilus", {"type": "Primary Mod"}) == "exilus"
    assert canonical_slot("R2_C4") == "R2_C4"
    assert slot_order("R1_C1") < slot_order("R2_C4") < slot_order("exilus")


def test_inferred_weapon_is_not_saved(analyzer):
    res = {"w_meta": {"name": "인식된 주무기", "is_inferred": True}, "mod_objs": []}
    assert analyzer.save_scanned_build(res) is None
    assert analyzer.build_store.list_builds() == []


def test_saved_build_round_trips_slots_and_order(analyzer):
    res = scan_result(analyzer, "Vulkar", {"R1_C2": "Vital Sense", "R2_C1": "Rupture"}, {"total_damage": 387.0, "crit_mult": 4.4})
    analyzer.save_scanned_build(res)
    build = analyzer.build_store.get_build("Vulkar")
    assert build["slots"] == {"R1_C2": "Vital Sense", "R2_C1": "Rupture"}
    assert build["panel"]["total_damage"] == 387.0
    assert build["panel_has_riven"] is False


def test_slot_edit_changes_mods_and_element_order(analyzer):
    res = scan_result(analyzer, "Vulkar", {"R1_C1": "Hellfire", "R1_C2": "Cryo Rounds", "R1_C3": "Infected Clip"})
    edited = analyzer.apply_slot_edits(res, {"R1_C1": "Hellfire", "R1_C2": "Infected Clip", "R1_C3": "Cryo Rounds", "R1_C4": ""})
    assert edited["metrics"]["elements"]["pairs"] == [("heat", "toxin", "gas")]
    assert [m["slot_name"] for m in edited["mod_objs"]] == ["R1_C1", "R1_C2", "R1_C3"]
    assert analyzer.result_slots(edited)["R1_C2"] == "Infected Clip"


def test_slot_edit_can_set_arcane(analyzer):
    res = scan_result(analyzer, "Vulkar", {"R1_C1": "Serration"})
    edited = analyzer.apply_slot_edits(res, {"R1_C1": "Serration", "arcane": "Primary Merciless"})
    assert edited["metrics"]["arcane"]["name"] == "Primary Merciless"
    assert "Primary Merciless 12스택" in edited["metrics"]["full_stack"]["assumptions"]
    analyzer.save_scanned_build(edited)
    assert analyzer.build_store.get_build("Vulkar")["arcane"] == "Primary Merciless"


def test_compare_without_build_uses_codex_and_says_so(analyzer):
    w = analyzer.indexer.fuzzy_match_weapon("Nataruk")
    res = analyzer.compare_riven_rolls(w, card(base_damage=2.517), card(heat=0.852, elemental_damage=0.852, multishot=0.82))
    # 900 * 3.517 versus 900 * 1.852 * 1.82, the same crit on both.
    assert res["before"]["final_dmg"] == pytest.approx(900 * 3.517)
    assert res["after"]["final_dmg"] == pytest.approx(900 * 1.852 * 1.82)
    assert "이전 옵션" in res["verdict"]
    assert any("스캔" in n for n in res["notes"])
    assert res["has_build"] is False


def test_compare_with_equipped_riven_treats_left_card_as_in_panel(analyzer):
    res = scan_result(analyzer, "Vulkar", {"R1_C1": "Serration", "R1_C2": RIVEN_MOD}, {"total_damage": 1000.0, "crit_chance": 0.5, "crit_mult": 3.0, "fire_rate": 2.0, "reload_time": 2.0, "magazine": 10.0})
    analyzer.save_scanned_build(res)
    w = analyzer.indexer.fuzzy_match_weapon("Vulkar")
    out = analyzer.compare_riven_rolls(w, card(base_damage=1.0), card(crit_chance=1.0))
    # Before must reproduce the panel exactly: the old roll is already in it.
    assert out["before"]["final_dmg"] == pytest.approx(1000.0)
    assert out["before"]["final_cc"] == pytest.approx(0.5)
    # After swaps the damage roll out (additive with Serration) and the crit roll in.
    assert out["after"]["final_dmg"] == pytest.approx(1000.0 * 2.65 / 3.65)
    assert out["after"]["final_cc"] == pytest.approx(0.5 + w["crit_chance"])


def test_compare_verdict_uses_sustained_dps_with_magazine_roll(analyzer):
    res = scan_result(analyzer, "Vulkar", {"R1_C1": RIVEN_MOD}, {"total_damage": 1000.0, "fire_rate": 2.0, "reload_time": 3.0, "magazine": 6.0})
    analyzer.save_scanned_build(res)
    w = analyzer.indexer.fuzzy_match_weapon("Vulkar")
    out = analyzer.compare_riven_rolls(w, card(reload_speed=0.0), card(magazine_capacity=1.0))
    assert out["after"]["burst_dps"] == pytest.approx(out["before"]["burst_dps"])
    assert out["after"]["sustained_dps"] > out["before"]["sustained_dps"]
    assert out["gain"] > 0


def test_build_without_riven_uses_first_empty_slot(analyzer):
    analyzer.save_scanned_build(scan_result(analyzer, "Vulkar", {"R1_C1": "Serration"}))
    out = analyzer.compare_riven_rolls(analyzer.indexer.fuzzy_match_weapon("Vulkar"), card(multishot=0.5), card(multishot=0.9))
    assert out["riven_slot"] == "R1_C2"
    assert "needs_slot_choice" not in out


def test_full_build_asks_which_mod_to_remove(analyzer):
    names = ["Serration", "Split Chamber", "Vital Sense", "Point Strike", "Hellfire", "Cryo Rounds", "Infected Clip", "Stormbringer"]
    analyzer.save_scanned_build(scan_result(analyzer, "Vulkar", dict(zip(GRID_SLOTS, names)), {"total_damage": 2000.0}))
    w = analyzer.indexer.fuzzy_match_weapon("Vulkar")
    ask = analyzer.compare_riven_rolls(w, card(multishot=0.5), card(multishot=0.9))
    assert ask["needs_slot_choice"] is True
    assert len(ask["choices"]) == 8

    out = analyzer.compare_riven_rolls(w, card(multishot=0.5), card(multishot=0.9), removed_slot="R1_C1")
    assert out["riven_slot"] == "R1_C1"
    assert out["before"]["final_dmg"] != 2000.0  # Serration left the panel, the riven came in.


def test_adopt_new_roll_updates_build_and_next_compare_starts_from_it(analyzer):
    res = scan_result(analyzer, "Vulkar", {"R1_C1": "Serration", "R1_C2": RIVEN_MOD}, {"total_damage": 1000.0, "fire_rate": 2.0})
    analyzer.save_scanned_build(res)
    w = analyzer.indexer.fuzzy_match_weapon("Vulkar")
    out = analyzer.compare_riven_rolls(w, card(base_damage=1.0), card(base_damage=2.0))
    assert "갱신" in analyzer.adopt_new_riven(out)
    build = analyzer.build_store.get_build("Vulkar")
    assert build["riven"] == {"base_damage": 2.0}
    assert build["panel_riven"] == {"base_damage": 1.0}

    # The saved build now evaluates with the new roll: 1000 at +265% additive becomes +365%.
    assert analyzer.evaluate_saved_build(build)["final_dmg"] == pytest.approx(1000.0 * 4.65 / 3.65)
    again = analyzer.compare_riven_rolls(w, card(base_damage=2.0), card(base_damage=1.0))
    assert again["before"]["final_dmg"] == pytest.approx(1000.0 * 4.65 / 3.65)
    assert again["after"]["final_dmg"] == pytest.approx(1000.0)


def test_adopt_without_build_explains(analyzer):
    w = analyzer.indexer.fuzzy_match_weapon("Nataruk")
    out = analyzer.compare_riven_rolls(w, card(multishot=0.5), card(multishot=0.9))
    assert "스캔" in analyzer.adopt_new_riven(out)
    assert analyzer.build_store.list_builds() == []


def test_unknown_riven_build_reads_panel_as_is(analyzer):
    analyzer.save_scanned_build(scan_result(analyzer, "Vulkar", {"R1_C1": RIVEN_MOD}, {"total_damage": 777.0}))
    build = analyzer.build_store.get_build("Vulkar")
    assert analyzer.evaluate_saved_build(build)["final_dmg"] == pytest.approx(777.0)
    assert "아직 모름" in analyzer.format_saved_build(build)


def test_format_saved_build_lists_slots(analyzer):
    analyzer.save_scanned_build(scan_result(analyzer, "Vulkar", {"R1_C1": "Vital Sense", "R2_C4": "Serration"}))
    text = analyzer.format_saved_build(analyzer.build_store.get_build("Vulkar"))
    assert "불카" in text and "바이탈 센스" in text and "서레이션" in text and "(빈 슬롯)" in text


def test_full_stack_counts_riven_only_once(analyzer):
    w = analyzer.indexer.fuzzy_match_weapon("Vulkar")
    out = analyzer.compare_riven_rolls(w, card(base_damage=1.0), card(base_damage=1.0))
    assert out["gain"] == pytest.approx(0.0)
    assert "거의 같습니다" in out["verdict"]


@pytest.mark.skipif(not os.path.exists(SAMPLE), reason="sample missing")
def test_real_reroll_screen_end_to_end(analyzer):
    res = analyzer.diagnose_screenshot(Image.open(SAMPLE))
    assert res["is_riven_compare"] is True
    assert res["weapon"] == "Nataruk"
    assert "이전 옵션" in res["verdict"]
    assert any("확대율" in u for u in res["unapplied"])
    assert any("상태 이상" in u for u in res["unapplied"])
