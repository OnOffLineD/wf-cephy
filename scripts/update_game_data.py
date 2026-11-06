"""Refreshes game data from Digital Extremes' Public Export and the drop table mirror.

Sources:
- Official Public Export: Korean and English names, descriptions and stats.
- WFCD warframe-items (MIT): the same export plus the per-attack data the damage engine needs.
- drops.warframestat.us: a JSON copy of the official drop table at warframe.com/droptables.

The wiki is not a source here: its terms forbid automated access without permission.
Everything is fetched and validated first, so a failed run changes no files.
"""
import json
import lzma
import os
import struct
import sys
import time
from typing import Any, Callable, Dict, List, Optional

import requests

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from scripts.game_catalog import build_catalog
from scripts.path_config import get_path, get_user_data_path, write_json_atomic

OFFICIAL_INDEX = 'https://origin.warframe.com/PublicExport/index_{lang}.txt.lzma'
OFFICIAL_MANIFEST = 'https://content.warframe.com/PublicExport/Manifest/{name}'
WFCD_FILE = 'https://raw.githubusercontent.com/WFCD/warframe-items/master/data/json/{name}'
DROP_TABLE = 'https://drops.warframestat.us/data/all.json'
DROP_TABLE_INFO = 'https://drops.warframestat.us/data/info.json'
USER_AGENT = 'WF-Companion/1.0'

ENGINE_FILES = ('Primary.json', 'Secondary.json', 'Melee.json', 'Warframes.json', 'Mods.json', 'Arch-Gun.json', 'Arch-Melee.json')
# A short list means a broken download, not a game update.
MIN_EXPORT_ITEMS = {'ExportWeapons': 500, 'ExportWarframes': 100, 'ExportUpgrades': 1000, 'ExportRelicArcane': 1000, 'ExportResources': 1000, 'ExportKeys': 20, 'ExportRegions': 200}
MIN_KEPT_RATIO = 0.9
CHECK_INTERVAL_SECONDS = 24 * 3600
KO_KEPT_FIELDS = ('name', 'description', 'levelStats', 'trigger', 'systemName')
COMPARED_STATS = ('totalDamage', 'criticalChance', 'criticalMultiplier', 'procChance', 'fireRate')
STAT_TOLERANCE = 0.01
MAX_LISTED_NAMES = 10


class DataValidationError(Exception):
    pass


def decompress_index(data: bytes) -> str:
    """The index is LZMA-alone with an unusual header that the standard reader rejects, so it is decoded raw."""
    props = data[0]
    pb = props // 45
    props %= 45
    lp = props // 9
    lc = props % 9
    dict_size = struct.unpack('<I', data[1:5])[0]
    decoder = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=[{'id': lzma.FILTER_LZMA1, 'dict_size': dict_size, 'lc': lc, 'lp': lp, 'pb': pb}])
    return decoder.decompress(data[13:]).decode('utf-8', 'replace')


def parse_index(text: str, lang: str) -> Dict[str, str]:
    """Maps "ExportWeapons" to its current file name; the hash suffix changes with every game update."""
    files = {}
    for line in text.splitlines():
        name = line.strip()
        if name:
            files[name.split('!')[0].replace(f'_{lang}.json', '').replace('.json', '')] = name
    return files


def _http_get(url: str) -> bytes:
    response = requests.get(url, headers={'User-Agent': USER_AGENT}, timeout=90)
    response.raise_for_status()
    return response.content


def _load_list(path: str) -> list:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


class GameDataUpdater:
    def __init__(self, data_dir: Optional[str] = None, fetch: Callable[[str], bytes] = _http_get, state_path: Optional[str] = None):
        self.data_dir = data_dir or get_path('data')
        self.raw_dir = os.path.join(self.data_dir, 'raw_wfcd')
        self.fetch = fetch
        self.state_path = state_path or get_user_data_path('game_data_state.json')

    def _state(self) -> Dict[str, Any]:
        try:
            with open(self.state_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def _save_state(self, state: Dict[str, Any]):
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        write_json_atomic(self.state_path, state)

    def _index(self, lang: str) -> Dict[str, str]:
        return parse_index(decompress_index(self.fetch(OFFICIAL_INDEX.format(lang=lang))), lang)

    def _versions(self) -> Dict[str, Any]:
        info = json.loads(self.fetch(DROP_TABLE_INFO))
        return {'official': self._index('ko'), 'drops': info.get('hash', '')}

    def check(self) -> Dict[str, Any]:
        """Compares version markers only: under a kilobyte per check, so it is cheap to run at startup."""
        versions = self._versions()
        state = self._state()
        known = state.get('versions', {})
        changed = sorted(k for k, v in versions['official'].items() if known.get('official', {}).get(k) != v)
        drops_changed = known.get('drops') != versions['drops']
        self._save_state({**state, 'last_check': time.time()})
        return {'changed': changed, 'drops_changed': drops_changed, 'has_update': bool(changed or drops_changed)}

    def due_for_check(self) -> bool:
        return time.time() - self._state().get('last_check', 0) >= CHECK_INTERVAL_SECONDS

    def _exports(self, lang: str, index: Dict[str, str], only: Optional[tuple] = None) -> Dict[str, Any]:
        exports = {}
        for key, file_name in index.items():
            if key == 'ExportManifest' or (only and key not in only):
                continue
            # The export contains raw line breaks inside strings, which strict JSON rejects.
            exports[key] = json.loads(self.fetch(OFFICIAL_MANIFEST.format(name=file_name)).decode('utf-8', 'replace'), strict=False)
        return exports

    @staticmethod
    def _validate_exports(exports: Dict[str, Any]):
        for key, minimum in MIN_EXPORT_ITEMS.items():
            items = exports.get(key, {}).get(key, [])
            if len(items) < minimum:
                raise DataValidationError(f"{key}: 항목 {len(items)}개 (최소 {minimum}개 필요)")

    def _fetch_engine_file(self, name: str) -> list:
        items = json.loads(self.fetch(WFCD_FILE.format(name=name)))
        current = _load_list(os.path.join(self.raw_dir, name))
        if not isinstance(items, list) or not items or len(items) < len(current) * MIN_KEPT_RATIO or not all(i.get('name') for i in items):
            raise DataValidationError(f"{name}: 비정상 데이터 (현재 {len(current)}개, 받은 데이터 {len(items) if isinstance(items, list) else '목록 아님'})")
        return items

    def _fetch_drops(self) -> Dict[str, Any]:
        drops = json.loads(self.fetch(DROP_TABLE))
        if not isinstance(drops, dict) or not drops.get('missionRewards') or not drops.get('relics'):
            raise DataValidationError("드롭 표: 필수 항목 없음")
        try:
            with open(os.path.join(self.raw_dir, 'drops_all.json'), 'r', encoding='utf-8') as f:
                current = len(json.load(f).get('relics', []))
        except (OSError, ValueError):
            current = 0
        if len(drops['relics']) < current * MIN_KEPT_RATIO:
            raise DataValidationError(f"드롭 표: 성유물 {len(drops['relics'])}개 (현재 {current}개)")
        return drops

    def _build_ko(self, exports: Dict[str, Any]) -> Dict[str, Any]:
        """Keeps older entries the export dropped, such as past weekly challenges, and refreshes the rest."""
        try:
            with open(os.path.join(self.raw_dir, 'ko.json'), 'r', encoding='utf-8') as f:
                merged = json.load(f)
        except (OSError, ValueError):
            merged = {}
        for payload in exports.values():
            for items in payload.values():
                if not isinstance(items, list):
                    continue
                for item in items:
                    if isinstance(item, dict) and item.get('uniqueName'):
                        entry = {k: item[k] for k in KO_KEPT_FIELDS if k in item}
                        if isinstance(entry.get('name'), str):
                            entry['name'] = entry['name'].replace('<ARCHWING> ', '')
                        merged[item['uniqueName']] = entry
        return merged

    @staticmethod
    def _changes(old: list, new: list) -> Dict[str, list]:
        old_by_id = {i.get('uniqueName') or i.get('name'): i for i in old}
        added, changed = [], []
        for item in new:
            previous = old_by_id.get(item.get('uniqueName') or item.get('name'))
            if previous is None:
                added.append(item['name'])
            elif any(previous.get(k) != item.get(k) for k in COMPARED_STATS):
                changed.append(item['name'])
        return {'added': added, 'stat_changed': changed}

    @staticmethod
    def _official_mismatches(engine: Dict[str, list], official_weapons: list) -> List[str]:
        """WFCD can lag the game by a few days, so its numbers are compared with the official ones."""
        official = {w.get('uniqueName'): w for w in official_weapons}
        mismatched = []
        for name in ('Primary.json', 'Secondary.json', 'Melee.json', 'Arch-Gun.json', 'Arch-Melee.json'):
            for item in engine.get(name, []):
                truth = official.get(item.get('uniqueName'))
                if truth and any(abs(float(item.get(k) or 0) - float(truth.get(k) or 0)) > STAT_TOLERANCE * max(abs(float(truth.get(k) or 0)), 1) for k in COMPARED_STATS):
                    mismatched.append(item['name'])
        return mismatched

    def _write_all(self, files: Dict[str, Any]):
        """Writes every temp file before swapping any, so a full disk can't leave a half-updated set."""
        temps = {}
        try:
            for path, data in files.items():
                os.makedirs(os.path.dirname(path), exist_ok=True)
                temp = f"{path}.tmp"
                with open(temp, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
                temps[path] = temp
        except OSError:
            for temp in temps.values():
                if os.path.exists(temp):
                    os.remove(temp)
            raise
        for path, temp in temps.items():
            os.replace(temp, path)

    def update(self) -> Dict[str, Any]:
        """Raises on a network or validation failure, leaving every data file as it was."""
        index_ko = self._index('ko')
        index_en = self._index('en')
        exports_ko = self._exports('ko', index_ko)
        exports_en = self._exports('en', index_en, only=tuple(MIN_EXPORT_ITEMS) + ('ExportSentinels', 'ExportGear'))
        self._validate_exports(exports_ko)
        self._validate_exports(exports_en)

        engine = {name: self._fetch_engine_file(name) for name in ENGINE_FILES}
        drops = self._fetch_drops()
        catalog = build_catalog(exports_ko, exports_en)
        versions = {'official': index_ko, 'drops': json.loads(self.fetch(DROP_TABLE_INFO)).get('hash', '')}

        changes = {name: self._changes(_load_list(os.path.join(self.raw_dir, name)), items) for name, items in engine.items()}
        files = {os.path.join(self.raw_dir, name): items for name, items in engine.items()}
        files[os.path.join(self.raw_dir, 'drops_all.json')] = drops
        files[os.path.join(self.raw_dir, 'ko.json')] = self._build_ko(exports_ko)
        files[os.path.join(self.data_dir, 'game_catalog.json')] = {'updated_at': time.strftime('%Y-%m-%d'), 'source': 'Warframe Public Export', 'entries': catalog}
        self._write_all(files)
        self._save_state({**self._state(), 'versions': versions, 'last_check': time.time(), 'last_update': time.time()})

        known_ids = {i.get('uniqueName') for items in engine.values() for i in items}
        return {
            'added': [n for c in changes.values() for n in c['added']],
            'stat_changed': [n for c in changes.values() for n in c['stat_changed']],
            'official_mismatches': self._official_mismatches(engine, exports_ko['ExportWeapons']['ExportWeapons']),
            'official_only': sum(1 for w in exports_ko['ExportWeapons']['ExportWeapons'] if w.get('uniqueName') not in known_ids),
            'catalog_entries': len(catalog),
        }


def format_report(report: Dict[str, Any]) -> str:
    def names(items: list) -> str:
        extra = f" 외 {len(items) - MAX_LISTED_NAMES}개" if len(items) > MAX_LISTED_NAMES else ''
        return ", ".join(items[:MAX_LISTED_NAMES]) + extra if items else "없음"

    lines = [
        "게임 데이터를 갱신했습니다.",
        f"• 공식 정보 항목: {report['catalog_entries']:,}개",
        f"• 새 항목: {names(report['added'])}",
        f"• 스펙이 바뀐 항목: {names(report['stat_changed'])}",
    ]
    if report['official_mismatches']:
        lines.append(f"• ⚠️ 공식 수치와 다른 무기(계산용 데이터 반영 지연 가능): {names(report['official_mismatches'])}")
    return "\n".join(lines)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    updater = GameDataUpdater()
    if '--check' in sys.argv:
        print(json.dumps(updater.check(), ensure_ascii=False, indent=2))
    else:
        print(format_report(updater.update()))
