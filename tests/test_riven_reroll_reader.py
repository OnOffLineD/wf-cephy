import os

import pytest
from PIL import Image

from scripts.riven_reroll_reader import (
    format_riven_stats,
    looks_like_reroll_screen,
    parse_riven_input,
    parse_stat_line,
    read_reroll_screen,
)

SAMPLE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ocrTestImg", "riven_reroll_nataruk.jpg")


@pytest.mark.parametrize("line, key, value", [
    ("+251.7% 피해", "base_damage", 2.517),
    ("+82% 멀 티샷", "multishot", 0.82),
    ("+41.10/0 탄창 용량", "magazine_capacity", 0.411),
    ("+85.20/0 6화염", "heat", 0.852),
    ("+85.2% 3화염", "heat", 0.852),
    ("-53.80/0 상태 이상 확률", "status_chance", -0.538),
    ("+120% 치명타 확률", "crit_chance", 1.2),
    ("+90.5% 치명타 피해", "crit_damage", 0.905),
    ("+60% 재장전 속도", "reload_speed", 0.6),
    ("+40% 공격 속도", "fire_rate", 0.4),
])
def test_parse_stat_line_handles_ocr_noise(line, key, value):
    parsed = parse_stat_line(line)
    assert parsed["key"] == key
    assert parsed["value"] == pytest.approx(value)


def test_parse_stat_line_keeps_stats_without_damage_effect_apart():
    parsed = parse_stat_line("+80.7% 확대율 증가")
    assert parsed["key"] is None
    assert parsed["label"] == "확대율 증가"
    assert parse_stat_line("나타루크 Visilis") is None


def test_element_stat_also_counts_as_elemental_damage():
    stats = parse_riven_input("화염 85.2 멀티샷 82")
    assert stats["heat"] == pytest.approx(0.852)
    assert stats["elemental_damage"] == pytest.approx(0.852)
    assert stats["multishot"] == pytest.approx(0.82)


def test_input_text_round_trips():
    stats = {"base_damage": 2.517, "status_chance": -0.538, "heat": 0.5, "elemental_damage": 0.5}
    assert parse_riven_input(format_riven_stats(stats)) == pytest.approx(stats)


def test_screen_detection():
    assert looks_like_reroll_screen("프느소 지 품/\n+80.7% 확대율 증가\n+251.7% 피해\n-53.8% 상태 이상 확률\n+85.2% 화염\n+41.1% 탄창 용량")
    assert not looks_like_reroll_screen("업그레이드/쿠바 자르 [40]\n치명타 확률 75%")
    assert not looks_like_reroll_screen("소지품/모드\n서레이션\n바이탈 센스")


@pytest.mark.skipif(not os.path.exists(SAMPLE), reason="sample missing")
def test_reads_real_reroll_screen():
    result = read_reroll_screen(Image.open(SAMPLE))
    assert result is not None
    old, new = result["old"], result["new"]
    assert old["stats"] == pytest.approx({"base_damage": 2.517, "status_chance": -0.538})
    assert [u["label"] for u in old["unapplied"]] == ["확대율 증가"]
    assert new["stats"] == pytest.approx({"heat": 0.852, "elemental_damage": 0.852, "magazine_capacity": 0.411, "multishot": 0.82})
    assert "isi" in old["name"]
    assert "satitin" in new["name"]
    assert "나타루크" in result["weapon_text"]
