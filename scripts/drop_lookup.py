"""Where-does-it-drop answers built directly from drops_all.json, so the model cannot invent a location."""
import json
import os
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from scripts.path_config import get_path

DROP_QUESTION = re.compile(r'어디|파밍|드랍|드롭|나와|나오|얻|구해|구하|떨어|떨궈|먹어|벌어')
BEST_QUESTION = re.compile(r'좋|제일|최고|효율|추천|빨리')
RELIC_NAME = re.compile(r'(axi|neo|meso|lith|requiem|액시|네오|메소|리스|레퀴엠)\s*([a-z]\d+)', re.I)
ITEM_COUNT = re.compile(r'^(?:(\d+)X\s+)?(?:([\d,]+)\s+)?(.+)$')
MIN_AUTO_NAME_LENGTH = 3
MAX_MISSIONS = 5
MAX_OTHERS = 3

# Resources are absent from the weapon and mod lists, so their Korean names are listed here.
ITEM_NAMES = {
    '엔도': ['Endo'],
    '포르마': ['Forma', 'Forma Blueprint', 'Forma Bundle'],
    '크레딧': ['Credits'],
    '쿠바': ['Kuva'],
    '강철 정수': ['Steel Essence'],
    '강철정수': ['Steel Essence'],
    '오로킨 반응로': ['Orokin Reactor', 'Orokin Reactor Blueprint'],
    '오로킨 촉매': ['Orokin Catalyst', 'Orokin Catalyst Blueprint'],
    '익시무스': ['Exilus Adapter', 'Exilus Weapon Adapter Blueprint'],
    '아야탄': ['Ayatan'],
    '비터스': ['Vitus Essence'],
    '비투스': ['Vitus Essence'],
}
PLANETS = {
    'Mercury': '수성', 'Venus': '금성', 'Earth': '지구', 'Mars': '화성', 'Ceres': '세레스', 'Jupiter': '목성', 'Europa': '유로파',
    'Saturn': '토성', 'Uranus': '천왕성', 'Neptune': '해왕성', 'Pluto': '명왕성', 'Sedna': '세드나', 'Eris': '에리스', 'Phobos': '포보스',
    'Deimos': '데이모스', 'Void': '보이드', 'Lua': '루아', 'Kuva Fortress': '쿠바 요새', 'Zariman': '자리만', 'Duviri': '두비리',
}
GAME_MODES = {
    'Survival': '생존', 'Defense': '방어', 'Mobile Defense': '이동방어', 'Interception': '감청', 'Capture': '포획', 'Exterminate': '섬멸',
    'Spy': '첩보', 'Rescue': '구출', 'Sabotage': '사보타주', 'Excavation': '발굴', 'Disruption': '교란', 'Assassination': '암살', 'Caches': '은닉처',
}
BOUNTY_TABLES = ('cetusBountyRewards', 'solarisBountyRewards', 'deimosRewards', 'zarimanRewards', 'entratiLabRewards', 'hexRewards')


def _parse_item(raw: str) -> Tuple[str, int]:
    """"3X 1,500 Credits Cache" is ("credits", 4500): counts multiply, and caches pay the same currency."""
    match = ITEM_COUNT.match(raw.strip())
    times, count, name = match.groups()
    amount = int(times or 1) * int((count or '1').replace(',', ''))
    return re.sub(r'\s+Cache$', '', name).strip().lower(), amount


def _rotated(rewards: Any) -> List[Tuple[str, Dict[str, Any]]]:
    if isinstance(rewards, dict):
        return [(rotation, item) for rotation, items in rewards.items() for item in items]
    return [('', item) for item in rewards or []]


def _chance_text(chance: float) -> str:
    return f"{chance:.2f}".rstrip('0').rstrip('.') + '%'


class DropIndex:
    def __init__(self, data_dir: str = 'data/raw_wfcd'):
        self.data_dir = get_path(data_dir) if not os.path.isabs(data_dir) else data_dir
        self._rows: Optional[Dict[str, List[Dict[str, Any]]]] = None
        self._names: Dict[str, Tuple[str, List[str]]] = {}
        self._relics: Dict[str, Dict[str, Any]] = {}

    def _read(self, name: str) -> Any:
        try:
            with open(os.path.join(self.data_dir, name), 'r', encoding='utf-8') as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def _load(self):
        if self._rows is not None:
            return
        rows: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        vaulted = {r['name']: bool(r.get('vaulted')) for r in self._read('Relics.json') or []}
        self._relics = {r['name'].lower().replace(' ', ''): r for r in self._read('Relics.json') or []}

        def add(raw_name, chance, kind, place, **extra):
            if not raw_name or chance is None:
                return
            name, amount = _parse_item(str(raw_name))
            rows[name].append({'item': name, 'amount': amount, 'chance': float(chance), 'kind': kind, 'place': place, **extra})

        drops = self._read('drops_all.json') or {}
        for planet, nodes in drops.get('missionRewards', {}).items():
            for node, info in nodes.items():
                if info.get('isEvent'):
                    continue
                mode = info.get('gameMode', '')
                # Some node names already end in their mode, like "Tier 1 (Hard)".
                mode_text = '' if mode.lower() in node.lower() else f" ({GAME_MODES.get(mode, mode)})"
                place = f"{PLANETS.get(planet, planet)} {node}{mode_text}"
                for rotation, item in _rotated(info.get('rewards')):
                    add(item.get('itemName'), item.get('chance'), 'mission', place, rotation=rotation)
        for table in drops.get('transientRewards', []):
            for item in table.get('rewards', []):
                add(item.get('itemName'), item.get('chance'), 'special', table.get('objectiveName', ''), rotation=item.get('rotation', ''))
        for key in BOUNTY_TABLES:
            for table in drops.get(key, []):
                for rotation, item in _rotated(table.get('rewards')):
                    add(item.get('itemName'), item.get('chance'), 'bounty', re.sub(r'\s+', ' ', table.get('bountyLevel', '')), rotation=rotation)
        for table in drops.get('keyRewards', []):
            for rotation, item in _rotated(table.get('rewards')):
                add(item.get('itemName'), item.get('chance'), 'special', table.get('keyName', ''), rotation=rotation)
        for relic in drops.get('relics', []):
            # Refinement only shifts the odds, so the unrefined state stands for the relic.
            if relic.get('state') != 'Intact':
                continue
            name = f"{relic.get('tier')} {relic.get('relicName')}"
            for item in relic.get('rewards', []):
                add(item.get('itemName'), item.get('chance'), 'relic', name, vaulted=vaulted.get(name, False))
        for table in drops.get('enemyModTables', []):
            enemy_chance = float(table.get('enemyModDropChance') or 100)
            for item in table.get('mods', []):
                add(item.get('modName'), enemy_chance * float(item.get('chance') or 0) / 100, 'enemy', table.get('enemyName', ''))
        for table in drops.get('enemyBlueprintTables', []):
            enemy_chance = float(table.get('enemyItemDropChance') or 100)
            for item in table.get('items', []):
                add(item.get('itemName'), enemy_chance * float(item.get('chance') or 0) / 100, 'enemy', table.get('enemyName', ''))
        for item in drops.get('sortieRewards', []):
            add(item.get('itemName'), item.get('chance'), 'special', '출격(Sortie)')

        self._rows = dict(rows)
        self._names = self._build_names()

    def _build_names(self) -> Dict[str, Tuple[str, List[str]]]:
        names = {re.sub(r'\s', '', k.lower()): (k, v) for k, v in ITEM_NAMES.items()}
        ko = self._read('ko.json') or {}
        for file_name in ('Primary.json', 'Secondary.json', 'Melee.json', 'Warframes.json', 'Mods.json'):
            for entry in self._read(file_name) or []:
                kr_name = (ko.get(entry.get('uniqueName')) or {}).get('name')
                if kr_name and len(kr_name) >= MIN_AUTO_NAME_LENGTH and entry.get('name'):
                    names.setdefault(re.sub(r'\s', '', kr_name.lower()), (kr_name, [entry['name']]))
        for arcane in self._read('weapon_arcanes.json') or []:
            if arcane.get('kr_name') and arcane.get('name'):
                names.setdefault(re.sub(r'\s', '', arcane['kr_name'].lower()), (arcane['kr_name'], [arcane['name']]))
        return names

    def resolve_item(self, query: str) -> Tuple[str, List[str]]:
        """Returns the item's display name and its English drop-table names, preferring the longest match."""
        self._load()
        compact = re.sub(r'\s', '', query.lower())
        for name in sorted(self._names, key=len, reverse=True):
            if name in compact:
                return self._names[name]
        for name in sorted(self._rows, key=len, reverse=True):
            if len(name) >= MIN_AUTO_NAME_LENGTH and name.isascii() and name.replace(' ', '') in compact:
                return name, [name]
        return '', []

    def _rows_for(self, english_names: List[str]) -> List[Dict[str, Any]]:
        found = []
        for name in english_names:
            lower = name.lower()
            found.extend(self._rows.get(lower, []))
            # Warframe and weapon names cover their parts, like "Hildryn Neuroptics Blueprint".
            found.extend(row for key, rows in self._rows.items() if key.startswith(lower + ' ') and lower not in ('forma', 'endo', 'credits', 'kuva') for row in rows)
        return found

    def _best_per_place(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        best: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            current = best.get(row['place'])
            if current is None or row['amount'] * row['chance'] > current['amount'] * current['chance']:
                best[row['place']] = row
        return sorted(best.values(), key=lambda r: r['amount'] * r['chance'], reverse=True)

    @staticmethod
    def _row_line(row: Dict[str, Any]) -> str:
        rotation = f" 로테이션 {row['rotation']}" if row.get('rotation') else ''
        amount = f"수량 {row['amount']:,}, " if row['amount'] > 1 else ''
        return f"• {row['place']}{rotation}: {amount}확률 {_chance_text(row['chance'])}"

    def answer_relic(self, query: str) -> Optional[str]:
        match = RELIC_NAME.search(query)
        if not match:
            return None
        self._load()
        tier = {'액시': 'axi', '네오': 'neo', '메소': 'meso', '리스': 'lith', '레퀴엠': 'requiem'}.get(match.group(1), match.group(1).lower())
        relic = self._relics.get(f"{tier}{match.group(2).lower()}")
        if not relic:
            return None
        state = '단종됨' if relic.get('vaulted') else '획득 가능'
        rewards = "\n".join(f"• {r.get('item')} ({r.get('type')})" for r in relic.get('rewards', []))
        return f"{relic['name']} 성유물 ({state}) 보상 목록:\n{rewards}"

    def answer(self, query: str) -> Optional[str]:
        """Returns None unless the question asks where an item drops and the tables list that item."""
        if not DROP_QUESTION.search(query):
            return None
        asked, english_names = self.resolve_item(query)
        rows = self._rows_for(english_names) if english_names else []
        if not rows:
            return None

        by_kind: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for row in rows:
            by_kind[row['kind']].append(row)

        lines = [f"{asked} 드롭 정보입니다 (드롭 표 기준, 기대 획득량 순):"]
        if by_kind['mission']:
            lines.append("[미션 보상]")
            lines += [self._row_line(r) for r in self._best_per_place(by_kind['mission'])[:MAX_MISSIONS]]
        for kind, label in (('bounty', '현상금'), ('special', '기타 보상'), ('enemy', '적 드롭')):
            if by_kind[kind]:
                lines.append(f"[{label}]")
                lines += [self._row_line(r) for r in self._best_per_place(by_kind[kind])[:MAX_OTHERS]]
        if by_kind['relic']:
            relics = {r['place']: r for r in by_kind['relic']}
            open_relics = sorted(name for name, r in relics.items() if not r.get('vaulted'))
            examples = f" (예: {', '.join(open_relics[:MAX_OTHERS])})" if open_relics else ''
            lines.append(f"[성유물] 전체 {len(relics)}종 중 획득 가능 {len(open_relics)}종{examples}")
        if BEST_QUESTION.search(query):
            lines.append("※ 드롭 표에는 확률만 있어 시간당 효율은 판단할 수 없습니다. 위 순서는 한 번 받을 때의 기대량 기준입니다.")
        return "\n".join(lines)
