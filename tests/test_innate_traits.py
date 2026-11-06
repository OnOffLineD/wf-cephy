import pytest

from scripts.innate_traits import INNATE_MOD, apply_innate_traits
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
