import json
import lzma
import os
from unittest.mock import MagicMock, patch

import pytest

from scripts.drop_lookup import DropIndex
from scripts.game_catalog import GameCatalog, build_catalog, clean_text
from scripts.guide_retriever import GuideRetriever
from scripts.llm_orchestrator import LLMOrchestrator
from scripts.path_config import get_path
from scripts.update_game_data import (
    DROP_TABLE, DROP_TABLE_INFO, ENGINE_FILES, MIN_EXPORT_ITEMS, DataValidationError, GameDataUpdater, decompress_index, format_report, parse_index,
)


def index_bytes(text: str) -> bytes:
    """The real index carries a raw LZMA1 stream behind a 13-byte header."""
    filters = [{"id": lzma.FILTER_LZMA1, "dict_size": 1 << 16, "lc": 3, "lp": 0, "pb": 2}]
    body = lzma.compress(text.encode("utf-8"), format=lzma.FORMAT_RAW, filters=filters)
    return bytes([0x5d]) + (1 << 16).to_bytes(4, "little") + b"\xff" * 8 + body


def fake_item(name, **extra):
    return {"uniqueName": f"/{name}", "name": name, "description": f"{name} 설명", **extra}


class FakeServer:
    """Serves a complete data set; tests break single pieces of it."""

    def __init__(self, drops_hash="h1"):
        self.overrides = {}
        self.drops_hash = drops_hash
        self.requests = []

    def _export(self, key):
        return {key: [fake_item(f"{key}{i}") for i in range(MIN_EXPORT_ITEMS.get(key, 1))]}

    def __call__(self, url):
        self.requests.append(url)
        for pattern, body in self.overrides.items():
            if pattern in url:
                if isinstance(body, Exception):
                    raise body
                return body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        if "index_" in url:
            lang = "ko" if "index_ko" in url else "en"
            names = [f"{k}_{lang}.json!00_abc" for k in list(MIN_EXPORT_ITEMS) + ["ExportSentinels", "ExportGear"]] + ["ExportManifest.json!00_x"]
            return index_bytes("\n".join(names))
        if "Manifest/" in url:
            key = url.split("Manifest/")[1].split("_")[0]
            return json.dumps(self._export(key)).encode("utf-8")
        if url == DROP_TABLE_INFO:
            return json.dumps({"hash": self.drops_hash}).encode("utf-8")
        if url == DROP_TABLE:
            return json.dumps({"missionRewards": {"Mercury": {}}, "relics": [{"tier": "Axi", "relicName": "A1", "state": "Intact", "rewards": []}]}).encode("utf-8")
        name = url.rsplit("/", 1)[1]
        return json.dumps([fake_item(f"{name}-{i}") for i in range(3)]).encode("utf-8")


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / "raw_wfcd").mkdir()
    return tmp_path


def updater_for(workspace, server):
    return GameDataUpdater(data_dir=str(workspace), fetch=server, state_path=str(workspace / "state.json"))


def snapshot(folder):
    return {p: open(os.path.join(root, p), "rb").read() for root, _, files in os.walk(folder) for p in files if p != "state.json"}


def test_index_decompresses_the_official_format():
    assert decompress_index(index_bytes("ExportWeapons_ko.json!00_abc\nExportManifest.json!00_x")).startswith("ExportWeapons_ko.json")


def test_index_maps_export_names_to_current_files():
    files = parse_index("ExportWeapons_ko.json!00_abc\r\n\r\nExportManifest.json!00_x\r\n", "ko")
    assert files == {"ExportWeapons": "ExportWeapons_ko.json!00_abc", "ExportManifest": "ExportManifest.json!00_x"}


def test_update_writes_every_file_and_reports(workspace):
    report = updater_for(workspace, FakeServer()).update()
    for name in ENGINE_FILES + ("drops_all.json", "ko.json"):
        assert (workspace / "raw_wfcd" / name).exists()
    catalog = json.loads((workspace / "game_catalog.json").read_text(encoding="utf-8"))
    assert report["catalog_entries"] == len(catalog["entries"]) > 0
    assert "Primary.json-0" in report["added"]
    assert "게임 데이터를 갱신했습니다" in format_report(report)


@pytest.mark.parametrize("piece, body", [
    ("Primary.json", ConnectionError("network down")),
    ("Primary.json", b"not json"),
    (DROP_TABLE, {"missionRewards": {}, "relics": []}),
    ("ExportWeapons_ko", {"ExportWeapons": []}),
])
def test_any_failure_changes_no_files(workspace, piece, body):
    server = FakeServer()
    updater = updater_for(workspace, server)
    updater.update()
    before = snapshot(workspace)
    server.overrides[piece] = body
    with pytest.raises(Exception):
        updater.update()
    assert snapshot(workspace) == before


def test_shrunken_download_is_refused(workspace):
    (workspace / "raw_wfcd" / "Primary.json").write_text(json.dumps([fake_item(f"w{i}") for i in range(100)]), encoding="utf-8")
    with pytest.raises(DataValidationError):
        updater_for(workspace, FakeServer()).update()


def test_export_with_raw_line_breaks_is_accepted(workspace):
    server = FakeServer()
    item = '{"ExportKeys": [' + ",".join('{"uniqueName": "/k%d", "name": "키", "description": "첫 줄\r\n둘째 줄"}' % i for i in range(MIN_EXPORT_ITEMS["ExportKeys"])) + "]}"
    server.overrides["ExportKeys_ko"] = item.encode("utf-8")
    updater_for(workspace, server).update()


def test_check_only_reads_version_markers_and_sees_changes(workspace):
    server = FakeServer()
    updater = updater_for(workspace, server)
    updater.update()
    server.requests.clear()
    assert updater.check()["has_update"] is False
    assert all("Manifest/" not in url and "githubusercontent" not in url for url in server.requests)
    server.drops_hash = "h2"
    assert updater.check()["drops_changed"] is True


def test_check_runs_once_a_day(workspace):
    updater = updater_for(workspace, FakeServer())
    assert updater.due_for_check() is True
    updater.check()
    assert updater.due_for_check() is False


def test_wfcd_numbers_are_compared_with_the_official_ones():
    engine = {"Primary.json": [fake_item("A", totalDamage=100, criticalChance=0.2), fake_item("B", totalDamage=100)]}
    official = [fake_item("A", totalDamage=150, criticalChance=0.2), fake_item("B", totalDamage=100.0001)]
    assert GameDataUpdater._official_mismatches(engine, official) == ["A"]


def test_old_korean_entries_survive_and_archwing_tag_is_removed(workspace):
    (workspace / "raw_wfcd" / "ko.json").write_text(json.dumps({"/old": {"name": "옛 항목"}}, ensure_ascii=False), encoding="utf-8")
    updater = updater_for(workspace, FakeServer())
    merged = updater._build_ko({"ExportWeapons": {"ExportWeapons": [{"uniqueName": "/w", "name": "<ARCHWING> 넉스", "extra": 1}]}})
    assert merged["/old"]["name"] == "옛 항목"
    assert merged["/w"] == {"name": "넉스"}


def test_catalog_joins_korean_and_english_by_unique_name():
    ko = {"ExportWeapons": {"ExportWeapons": [{"uniqueName": "/t", "name": "토리드", "description": "독성 투사", "damagePerShot": [0, 0, 0, 0, 0, 0, 140], "totalDamage": 140, "criticalChance": 0.15, "productCategory": "LongGuns"}]},
          "ExportWarframes": {"ExportWarframes": [{"uniqueName": "/h", "name": "힐드린", "health": 100, "passiveDescription": "오브 |PERCENT|% 전환", "abilities": [{"abilityName": "밸리스티스", "description": "<DT_FIRE>발사"}]}]},
          "ExportRelicArcane": {"ExportRelicArcane": [{"uniqueName": "/r", "name": "성유물", "relicRewards": []}, {"uniqueName": "/a", "name": "아케인 가디언", "levelStats": [{"stats": ["약함"]}, {"stats": ["강함"]}]}]}}
    en = {"ExportWeapons": {"ExportWeapons": [{"uniqueName": "/t", "name": "Torid"}]}}
    entries = {e["ko"]: e for e in build_catalog(ko, en)}
    assert entries["토리드"]["en"] == "Torid"
    assert entries["토리드"]["damage"] == {"독성": 140}
    assert entries["토리드"]["category"] == "주무기"
    assert entries["힐드린"]["passive"] == "오브 일정% 전환"
    assert entries["힐드린"]["abilities"][0]["description"] == "발사"
    assert entries["아케인 가디언"]["max_rank_effect"] == "강함"
    assert "성유물" not in entries


def test_clean_text_handles_game_markup():
    assert clean_text(["<LINE_SEPARATOR>첫째\r\n둘째", "|VAL|%"]) == "첫째 둘째 일정%"


def test_shipped_catalog_has_each_kind_with_korean_text():
    catalog = GameCatalog()
    kinds = {e["kind"] for e in catalog.entries}
    assert {"weapon", "warframe", "mod", "arcane", "quest", "resource"} <= kinds
    hildryn = catalog.by_name["힐드린"]
    assert hildryn["kind"] == "warframe" and hildryn["abilities"] and hildryn["description"]


@pytest.fixture(scope="module")
def retriever():
    return GuideRetriever()


def test_warframe_card_explains_the_warframe(retriever):
    card = retriever.retrieve("힐드린 어빌리티 알려줘", top_k=1)[0]
    assert "힐드린" in card["title"] or "Hildryn" in card["title"]
    assert "어빌리티" in card["text"] and "설명" in card["text"]


def test_weapon_card_has_official_description(retriever):
    text = retriever.retrieve("토리드 설명", top_k=1)[0]["text"]
    assert "독성" in text and "치명타 확률" in text


@pytest.mark.parametrize("query, word", [("아케인 에너자이즈 효과 뭐야", "최대 랭크"), ("서레이션 효과 뭐야", "최대 랭크"), ("포르마 뭐야", "설명")])
def test_mods_arcanes_and_resources_have_cards(retriever, query, word):
    top = retriever.retrieve(query, top_k=1)[0]
    assert top["type"] == "weapon_spec" and word in top["text"]


def test_guide_titled_after_the_subject_stays_first(retriever):
    assert "오버가드" in retriever.retrieve("오버가드 뭐야", top_k=1)[0]["title"]


@pytest.mark.parametrize("query", ["오늘 뭐하지", "베루스 어때", "피곤하다"])
def test_everyday_words_get_no_card(retriever, query):
    assert retriever.retrieve(query, top_k=1) == []


def test_arch_guns_are_searchable(retriever):
    assert "Imperator" in retriever.retrieve("임페라토르 스펙", top_k=1)[0]["title"]


def test_relic_availability_comes_from_current_drop_tables():
    drops = DropIndex()
    drops._load()
    obtainable = sorted(drops._obtainable)[0]
    assert "획득 가능" in drops.answer_relic(obtainable)
    vaulted = next(r["name"] for r in drops._relics.values() if r["name"].lower() not in drops._obtainable and r["name"].split()[0] in ("Axi", "Neo", "Meso", "Lith"))
    assert "단종됨" in drops.answer_relic(vaulted)


def test_catalog_names_reach_the_drop_lookup():
    assert "오로킨" in DropIndex().answer("오로킨 반응로 어디서 구해")


@pytest.fixture
def orc():
    orchestrator = LLMOrchestrator()
    orchestrator._call_llm = MagicMock(return_value=None)
    return orchestrator


def test_update_command_reports_and_reloads(orc):
    fake = MagicMock()
    fake.update.return_value = {"added": ["새 무기"], "stat_changed": [], "official_mismatches": [], "official_only": 0, "catalog_entries": 10}
    old_drops = orc.drop_index
    with patch("scripts.llm_orchestrator.GameDataUpdater", return_value=fake):
        res = orc.chat("/데이터 갱신")
    assert res["type"] == "system" and "새 무기" in res["report"]
    assert orc.drop_index is not old_drops


def test_update_failure_keeps_data_and_says_so(orc):
    fake = MagicMock()
    fake.update.side_effect = ConnectionError("network down")
    old_drops = orc.drop_index
    with patch("scripts.llm_orchestrator.GameDataUpdater", return_value=fake):
        res = orc.chat("/데이터 갱신")
    assert "기존 데이터는 그대로" in res["report"]
    assert orc.drop_index is old_drops


def test_check_command_does_not_download_data(orc):
    fake = MagicMock()
    fake.check.return_value = {"has_update": True}
    with patch("scripts.llm_orchestrator.GameDataUpdater", return_value=fake):
        res = orc.chat("/데이터 확인")
    assert "/데이터 갱신" in res["report"]
    fake.update.assert_not_called()


def test_wiki_is_not_an_automated_source():
    with open(get_path("scripts", "update_game_data.py"), encoding="utf-8") as f:
        source = f.read()
    assert "wiki.warframe.com" not in source
    assert not os.path.exists(get_path("scripts", "wiki_ingestor.py"))
