from unittest.mock import MagicMock

import pytest

from scripts.innate_traits import INNATE_MOD, apply_innate_traits, is_adversary, parse_bonus_answer
from scripts.llm_orchestrator import LLMOrchestrator
from scripts.screen_mod_analyzer import ScreenModAnalyzer
from scripts.warframe_damage_engine import WarframeDamageEngine
from scripts.wf_data_indexer import WFDataIndexer


@pytest.fixture(scope="module")
def ix():
    return WFDataIndexer()


@pytest.fixture(scope="module")
def motovore(ix):
    return ix.weapons_index["coda motovore"]


def mods(ix, *names):
    return [ix.match_mod(n, "Melee") for n in names]


def test_motovore_matches_the_arsenal_panel(ix, motovore):
    # In-game panel with Auger Strike + Jugulus Barbs: puncture 1,133.2, impact 83.3, slash 83.4.
    # Its total 1,413.5 also has 113.6 of bonus magnetic, which comes from the panel, not from mods.
    res = WarframeDamageEngine().compute_metrics(motovore, mod_objs=mods(ix, "Auger Strike", "Jugulus Barbs"))
    types = res["elements"]["types"]
    assert types["puncture"] == pytest.approx(1133.2, abs=0.5)
    assert types["impact"] == pytest.approx(83.3, abs=0.1)
    assert types["slash"] == pytest.approx(83.4, abs=0.1)
    assert res["final_dmg"] == pytest.approx(1413.5 - 113.6, abs=0.5)


@pytest.mark.parametrize("mod, label", [("Buzz Kill", "베기 휠"), ("Heavy Trauma", "충격 휠"), ("Auger Strike", "관통 휠")])
def test_wheel_follows_the_strongest_physical_mod(ix, motovore, mod, label):
    res = WarframeDamageEngine().compute_metrics(motovore, mod_objs=mods(ix, mod))
    assert any(label in line for line in res["innate"])


def test_impact_wheel_adds_attack_speed_when_the_panel_has_none(ix, motovore):
    res = WarframeDamageEngine().compute_metrics(motovore, mod_objs=mods(ix, "Heavy Trauma"))
    assert res["final_fr"] == pytest.approx(1.4)


def test_panel_values_win_over_the_trait(ix, motovore):
    left = {"total_damage": 1413.5, "fire_rate": 1.1}
    res = WarframeDamageEngine().compute_metrics(motovore, left_stats=left, mod_objs=mods(ix, "Heavy Trauma"))
    assert res["final_dmg"] == pytest.approx(1413.5)
    assert res["final_fr"] == pytest.approx(1.1)


def test_trait_is_applied_once(ix, motovore):
    once = apply_innate_traits(motovore, mods(ix, "Auger Strike"))
    twice = apply_innate_traits(motovore, once)
    assert twice is once
    assert once[0]["puncture"] == pytest.approx(7.2)
    # Full stack calls compute_metrics with mods it already prepared.
    full = WarframeDamageEngine().compute_full_stack(motovore, mod_objs=mods(ix, "Auger Strike", "Jugulus Barbs"))
    assert full["final_dmg"] == pytest.approx(1413.5 - 113.6, abs=0.5)


def test_other_weapons_are_unchanged(ix):
    hammer = ix.weapons_index["fragor"]
    prepared = apply_innate_traits(hammer, mods(ix, "Auger Strike"))
    assert prepared[0]["puncture"] == pytest.approx(1.2)
    assert not any(m.get("name") == INNATE_MOD for m in prepared)
    assert WarframeDamageEngine().compute_metrics(hammer, mod_objs=prepared)["innate"] == []


def test_adversary_weapons_are_recognised(ix):
    for name in ("kuva zarr", "tenet cycron", "coda hema", "coda motovore", "kuva ayanga"):
        assert is_adversary(ix.weapons_index[name])
    assert not is_adversary(ix.weapons_index["fragor"])


@pytest.mark.parametrize("text, expected", [
    ("자성 45", ("magnetic", 0.45)),
    ("전기 60%", ("electric", 0.6)),
    ("보너스 속성은 방사능 52%입니다", ("radiation", 0.52)),
    ("독", ("toxin", None)),
    ("impact 30", ("impact", 0.3)),
])
def test_bonus_answers_are_read(text, expected):
    assert parse_bonus_answer(text) == expected


@pytest.mark.parametrize("text", ["화염 약점 뭐야?", "치확 150 치피 120", "자성 좋아?", "오늘 냉기 속성 보스 누구야"])
def test_other_messages_are_not_bonus_answers(text):
    assert parse_bonus_answer(text) is None


def test_motovore_panel_total_with_its_magnetic_bonus(ix, motovore):
    # The same panel's magnetic row: 113.6 = 250 x 45.44% bonus. With it the whole total matches.
    left = {"valence_magnetic": 113.6 / 250}
    res = WarframeDamageEngine().compute_metrics(motovore, left_stats=left, mod_objs=mods(ix, "Auger Strike", "Jugulus Barbs"))
    assert res["final_dmg"] == pytest.approx(1413.5, abs=0.5)
    assert res["elements"]["types"]["magnetic"] == pytest.approx(113.6, abs=0.2)
    assert any("자성 45.44%" in line for line in res["innate"])


def test_impact_bonus_adds_to_impact_instead_of_replacing_it(ix):
    zarr = ix.weapons_index["kuva zarr"]
    engine = WarframeDamageEngine()
    plain = engine.compute_metrics(zarr)["elements"]["types"]
    boosted = engine.compute_metrics(zarr, left_stats={"valence_impact": 0.6})["elements"]["types"]
    attacks = zarr["attacks"][0]["damage"]
    assert boosted["impact"] == pytest.approx(plain.get("impact", 0.0) + 0.6 * sum(attacks.values()), rel=1e-3)
    assert all(boosted[t] == pytest.approx(v) for t, v in plain.items() if t != "impact")


@pytest.fixture(scope="module")
def analyzer():
    return ScreenModAnalyzer()


def scan(analyzer, ix, motovore, stats):
    question = analyzer._resolve_bonus(motovore, stats)
    mod_objs = mods(ix, "Auger Strike", "Jugulus Barbs")
    res = {"w_meta": motovore, "stats": stats, "mod_objs": mod_objs, "detected_mods": [m["kr_name"] for m in mod_objs],
           "metrics": {}, "equipped_slot_count": 2, "message": "", "review_message": ""}
    return question, res


def test_asks_for_the_bonus_and_applies_the_answer(analyzer, ix, motovore):
    analyzer.bonus_elements.clear()
    question, res = scan(analyzer, ix, motovore, {})
    assert "보너스 속성" in question
    analyzer.pending_bonus = res

    assert analyzer.resume_pending_bonus("화염 약점 뭐야?") is None
    assert analyzer.has_pending_bonus()
    assert analyzer.resume_pending_bonus("자성 80")["success"] is False

    answered = analyzer.resume_pending_bonus("자성 45")
    assert answered["success"] and not analyzer.has_pending_bonus()
    assert res["stats"] == {"valence_magnetic": 0.45}
    assert any("자성 45%" in line for line in res["metrics"]["innate"])
    assert "자성 45%" in res["review_message"]


def test_remembers_the_answer_but_the_panel_wins(analyzer, ix, motovore):
    analyzer.bonus_elements.clear()
    analyzer.bonus_elements[motovore["name"]] = ("magnetic", 0.45)
    stats = {}
    note, _ = scan(analyzer, ix, motovore, stats)
    assert stats == {"valence_magnetic": 0.45} and "지난번" in note
    assert not analyzer.has_pending_bonus()

    panel = {"valence_heat": 0.6}
    assert scan(analyzer, ix, motovore, panel)[0] == ""
    assert analyzer.bonus_elements[motovore["name"]] == ("heat", 0.6)


def test_non_adversary_weapons_are_not_asked(analyzer, ix):
    assert analyzer._resolve_bonus(ix.weapons_index["fragor"], {}) == ""
    assert not analyzer.has_pending_bonus()


def test_chat_answer_reaches_the_waiting_scan(analyzer, ix, motovore):
    analyzer.bonus_elements.clear()
    _, res = scan(analyzer, ix, motovore, {})
    analyzer.pending_bonus = res
    orc = LLMOrchestrator()
    orc.diagnoser = analyzer
    orc.chat_smalltalk = MagicMock(return_value="[MOOD:happy:1] 잡담")
    reply = orc.chat("전기 60")
    assert reply["type"] == "DIAGNOSIS_CLARIFIED" and reply["data"] is res
    assert res["stats"] == {"valence_electric": 0.6}
