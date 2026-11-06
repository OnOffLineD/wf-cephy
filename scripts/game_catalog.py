"""Official game text and stats: descriptions, abilities, mods, arcanes, quests and resources in Korean."""
import json
import os
import re
from typing import Any, Dict, List, Optional

from scripts.path_config import get_path

CATALOG_PATH = 'data/game_catalog.json'
# Order of the damagePerShot array in the official export, checked against Hek and Torid.
DAMAGE_TYPES = ('충격', '관통', '베기', '화염', '냉기', '전기', '독성', '폭발', '방사능', '가스', '자성', '바이러스', '부식', '보이드', '타우')
WEAPON_CATEGORIES = {
    'LongGuns': '주무기', 'Pistols': '보조무기', 'Melee': '근접 무기', 'SpaceGuns': '아크건', 'SpaceMelee': '아크 근접 무기',
    'SentinelWeapons': '동반자 무기', 'SpecialItems': '특수 무기', 'OperatorAmps': '오퍼레이터 앰프',
}
KIND_LABELS = {
    'weapon': '무기', 'warframe': '워프레임', 'companion': '동반자', 'mod': '모드', 'arcane': '아케인', 'quest': '퀘스트', 'resource': '자원', 'gear': '장비',
}
# Earlier kinds win when two entries share a name, like a weapon and its augment mod.
KIND_PRIORITY = ('weapon', 'warframe', 'companion', 'arcane', 'quest', 'mod', 'gear', 'resource')
SKIPPED_RESOURCE_PATHS = ('/Lotus/Types/Items/ShipDecos', '/Lotus/Types/Recipes', '/Lotus/Objects')
MAX_RUN_WORDS = 5


def clean_text(value: Any) -> str:
    """Strips the game's colour tags and fills value slots that the export leaves blank."""
    if isinstance(value, list):
        value = " ".join(str(v) for v in value)
    text = re.sub(r'<[^>]+>', '', str(value or ''))
    text = re.sub(r'\|[A-Z_0-9]+\|', '일정', text)
    return re.sub(r'\s*\r?\n\s*', ' ', text).strip()


def _compact(text: str) -> str:
    return re.sub(r'[^0-9a-z가-힣]', '', text.lower())


def _rounded(value: Any, digits: int = 3) -> float:
    return round(float(value or 0), digits)


def _weapon_entry(item: Dict[str, Any]) -> Dict[str, Any]:
    damage = {name: _rounded(v, 1) for name, v in zip(DAMAGE_TYPES, item.get('damagePerShot') or []) if v}
    entry = {
        'category': WEAPON_CATEGORIES.get(item.get('productCategory'), item.get('productCategory', '')),
        'mastery': item.get('masteryReq', 0),
        'damage': damage,
        'total_damage': _rounded(item.get('totalDamage'), 1),
        'crit_chance': _rounded(item.get('criticalChance')),
        'crit_mult': _rounded(item.get('criticalMultiplier')),
        'status_chance': _rounded(item.get('procChance')),
        'fire_rate': _rounded(item.get('fireRate')),
    }
    for source, target in (('magazineSize', 'magazine'), ('reloadTime', 'reload'), ('multishot', 'multishot'), ('trigger', 'trigger'), ('range', 'range')):
        if item.get(source):
            entry[target] = item[source]
    return entry


def _warframe_entry(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'mastery': item.get('masteryReq', 0),
        'health': item.get('health'),
        'shield': item.get('shield'),
        'armor': item.get('armor'),
        'energy': item.get('power'),
        'sprint': _rounded(item.get('sprintSpeed')),
        'passive': clean_text(item.get('passiveDescription')),
        'abilities': [{'name': clean_text(a.get('abilityName')), 'description': clean_text(a.get('description'))} for a in item.get('abilities', [])],
    }


def _ranked_entry(item: Dict[str, Any]) -> Dict[str, Any]:
    levels = item.get('levelStats') or []
    return {
        'rarity': item.get('rarity', ''),
        'max_rank_effect': clean_text(levels[-1].get('stats')) if levels else '',
        'max_rank': max(len(levels) - 1, 0),
    }


def build_catalog(ko: Dict[str, Any], en: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Joins the Korean and English exports by uniqueName; both are the game's own text."""
    def english_names(export, key):
        return {e['uniqueName']: e.get('name', '') for e in en.get(export, {}).get(key, []) if e.get('uniqueName')}

    def add(kind, export, key, build=None, keep=lambda item: True):
        names = english_names(export, key)
        for item in ko.get(export, {}).get(key, []):
            name = clean_text(item.get('name'))
            if not name or not keep(item):
                continue
            entry = {'kind': kind, 'ko': name, 'en': clean_text(names.get(item.get('uniqueName'))), 'description': clean_text(item.get('description'))}
            entries.append({**entry, **(build(item) if build else {})})

    entries: List[Dict[str, Any]] = []
    add('weapon', 'ExportWeapons', 'ExportWeapons', _weapon_entry)
    add('weapon', 'ExportWeapons', 'ExportRailjackWeapons', _weapon_entry)
    add('warframe', 'ExportWarframes', 'ExportWarframes', _warframe_entry)
    add('companion', 'ExportSentinels', 'ExportSentinels', _warframe_entry)
    add('mod', 'ExportUpgrades', 'ExportUpgrades', _ranked_entry)
    add('arcane', 'ExportRelicArcane', 'ExportRelicArcane', _ranked_entry, keep=lambda item: 'relicRewards' not in item)
    add('quest', 'ExportKeys', 'ExportKeys', keep=lambda item: bool(item.get('description')))
    add('gear', 'ExportGear', 'ExportGear')
    add('resource', 'ExportResources', 'ExportResources', keep=lambda item: bool(item.get('description')) and not str(item.get('uniqueName', '')).startswith(SKIPPED_RESOURCE_PATHS))
    return entries


class GameCatalog:
    def __init__(self, path: str = CATALOG_PATH):
        self.path = get_path(path) if not os.path.isabs(path) else path
        self.by_name: Dict[str, Dict[str, Any]] = {}
        self.entries: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                self.entries = json.load(f).get('entries', [])
        except (OSError, ValueError):
            return
        ranked = sorted(self.entries, key=lambda e: KIND_PRIORITY.index(e['kind']) if e.get('kind') in KIND_PRIORITY else len(KIND_PRIORITY))
        for entry in ranked:
            for name in (entry.get('ko'), entry.get('en')):
                key = _compact(name or '')
                if len(key) >= 2:
                    self.by_name.setdefault(key, entry)

    def find(self, words: List[str]) -> Optional[Dict[str, Any]]:
        """Whole word runs only, longest first, so common words inside a question can't match an item."""
        compact_words = [_compact(w) for w in words]
        for size in range(min(MAX_RUN_WORDS, len(compact_words)), 0, -1):
            for i in range(len(compact_words) - size + 1):
                entry = self.by_name.get(''.join(compact_words[i:i + size]))
                if entry:
                    return entry
        return None

    @staticmethod
    def details(entry: Dict[str, Any]) -> List[str]:
        """Lines that the search card adds on top of any stats it already shows."""
        lines = [f"- 설명: {entry['description']}"] if entry.get('description') else []
        if entry.get('mastery'):
            lines.append(f"- 필요 마스터리: {entry['mastery']}")
        if entry.get('passive'):
            lines.append(f"- 패시브: {entry['passive']}")
        lines += [f"- 어빌리티 {a['name']}: {a['description']}" for a in entry.get('abilities', [])]
        return lines

    @classmethod
    def card_text(cls, entry: Dict[str, Any]) -> str:
        label = KIND_LABELS.get(entry.get('kind'), '항목')
        lines = [f"### [공식 {label} 정보: {entry.get('ko')} ({entry.get('en')})]"]
        if entry.get('kind') == 'weapon':
            damage = ", ".join(f"{k} {v}" for k, v in entry.get('damage', {}).items())
            lines += [
                f"- 분류: {entry.get('category')}",
                f"- 기본 피해량: {entry.get('total_damage')} ({damage})",
                f"- 치명타 확률: {round(entry.get('crit_chance', 0) * 100, 1)}%",
                f"- 치명타 배수: {entry.get('crit_mult')}x",
                f"- 상태이상 확률: {round(entry.get('status_chance', 0) * 100, 1)}%",
                f"- 연사력: {entry.get('fire_rate')}",
            ]
            if entry.get('magazine'):
                lines.append(f"- 탄창: {entry['magazine']}, 재장전: {entry.get('reload')}초")
        elif entry.get('kind') in ('warframe', 'companion'):
            lines += [f"- 체력: {entry.get('health')}", f"- 실드: {entry.get('shield')}", f"- 방어력: {entry.get('armor')}", f"- 에너지: {entry.get('energy')}"]
        elif entry.get('max_rank_effect'):
            lines.append(f"- 최대 랭크({entry.get('max_rank')}) 효과: {entry['max_rank_effect']}")
        return "\n".join(lines + cls.details(entry))
