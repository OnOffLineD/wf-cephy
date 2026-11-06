import copy
import html
import json
import os
import re
import shutil
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

import requests

from scripts.path_config import get_user_data_path, write_json_atomic

UNKNOWN = "확인 불가"
EXPIRED = "갱신 대기"

# Plains of Eidolon cycle. One known night-to-day switch plus the cycle length estimates it when the API is down.
CETUS_DAY_START = datetime(2026, 11, 4, 11, 40, tzinfo=timezone.utc)
CETUS_CYCLE_SECONDS = 8998.8748
CETUS_NIGHT_SECONDS = 3000.0

DUVIRI_STATES = {"sorrow": "슬픔", "fear": "공포", "joy": "기쁨", "anger": "분노", "envy": "질투"}
FACTIONS = {
    "Grineer": "그리니어", "Corpus": "코퍼스", "Infested": "인페스티드", "Orokin": "오로킨", "Corrupted": "오로킨",
    "Narmer": "나르메르", "Sentient": "센티언트", "Murmur": "머머", "The Murmur": "머머",
}
ARCHONS = {"Archon Amar": "집정관 아마르", "Archon Boreal": "집정관 보리얼", "Archon Nira": "집정관 나이라"}


def parse_time(value: Any) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def format_seconds(seconds: float) -> str:
    minutes = int(seconds // 60)
    if minutes < 1:
        return "1분 미만"
    days, minutes = divmod(minutes, 1440)
    hours, minutes = divmod(minutes, 60)
    if days:
        return f"{days}일 {hours}시간" if hours else f"{days}일"
    if hours:
        return f"{hours}시간 {minutes}분" if minutes else f"{hours}시간"
    return f"{minutes}분"


def format_remaining(expiry: Any, now: datetime) -> str:
    target = parse_time(expiry)
    if target is None:
        return ""
    seconds = (target - now).total_seconds()
    return format_seconds(seconds) if seconds > 0 else EXPIRED


def cetus_estimate(now: datetime) -> Dict[str, Any]:
    elapsed = (now - CETUS_DAY_START).total_seconds() % CETUS_CYCLE_SECONDS
    day_seconds = CETUS_CYCLE_SECONDS - CETUS_NIGHT_SECONDS
    is_night = elapsed >= day_seconds
    left = (CETUS_CYCLE_SECONDS if is_night else day_seconds) - elapsed
    return {"isNight": is_night, "timeLeft": format_seconds(left), "estimated": True}


def _parse_cetus(raw: Optional[Dict[str, Any]], now: datetime) -> Dict[str, Any]:
    expiry = parse_time((raw or {}).get("expiry"))
    if expiry is not None and expiry > now:
        info = {"isNight": raw.get("isDay") is False, "timeLeft": format_remaining(expiry.isoformat(), now), "estimated": False}
    else:
        info = cetus_estimate(now)
    info["state"] = "밤" if info["isNight"] else "낮"
    info["huntingTip"] = "아이돌론 사냥 가능" if info["isNight"] else "아이돌론은 밤에만 등장"
    return info


def _parse_duviri(raw: Optional[Dict[str, Any]], translate: Callable[[str], str]) -> Dict[str, Any]:
    if not raw:
        return {"state": UNKNOWN, "warframes": [], "hard": []}
    choices = {c.get("category"): c.get("choices") or [] for c in raw.get("choices") or []}
    return {
        "state": DUVIRI_STATES.get(raw.get("state"), raw.get("state") or UNKNOWN),
        "warframes": [translate(n) for n in choices.get("normal", [])],
        "hard": [translate(n) for n in choices.get("hard", [])],
    }


def _parse_mission(raw: Optional[Dict[str, Any]], now: datetime, names: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    if not raw:
        return {"boss": UNKNOWN, "faction": "", "timeLeft": ""}
    boss = raw.get("boss") or UNKNOWN
    faction = raw.get("faction") or ""
    return {
        "boss": (names or {}).get(boss, boss),
        "faction": FACTIONS.get(faction, faction),
        "timeLeft": format_remaining(raw.get("expiry"), now),
    }


def _parse_void_trader(raw: Optional[Dict[str, Any]], now: datetime) -> Dict[str, Any]:
    if not raw:
        return {"active": False, "status": UNKNOWN, "location": "", "eta": ""}
    start, end = parse_time(raw.get("activation")), parse_time(raw.get("expiry"))
    active = bool(start and end and start <= now < end)
    return {
        "active": active,
        "status": "방문 중" if active else "도착 전",
        "location": raw.get("location") or "",
        "eta": format_remaining(raw.get("expiry") if active else raw.get("activation"), now),
    }


def parse_world_state(raw: Dict[str, Any], now: Optional[datetime] = None, translate: Optional[Callable[[str], str]] = None) -> Dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    translate = translate or (lambda name: name)
    duviri = _parse_duviri(raw.get("duviriCycle"), translate)
    return {
        "cetus": _parse_cetus(raw.get("cetusCycle"), now),
        "duviri": {"state": duviri["state"], "warframes": duviri["warframes"]},
        "sortie": _parse_mission(raw.get("sortie"), now),
        "archon": _parse_mission(raw.get("archonHunt"), now, ARCHONS),
        "void_trader": _parse_void_trader(raw.get("voidTrader"), now),
        # The Steel Path weapon choices at the Circuit are the current Incarnon adapter rotation.
        "incarnon": {"weapons": duviri["hard"]},
    }


class WorldStateTracker:
    API_URL = "https://api.warframestat.us/pc"
    ENDPOINTS = ("cetusCycle", "duviriCycle", "sortie", "archonHunt", "voidTrader")
    REQUEST_TIMEOUT = 8
    DEFAULT_CHECKLIST = [
        {"id": "daily_sortie", "type": "daily", "text": "일일 출격 (Sortie) 3단계 클리어", "done": False},
        {"id": "daily_sp_incursion", "type": "daily", "text": "강철의 길 일일 침공 (에센스 5개)", "done": False},
        {"id": "daily_simaris", "type": "daily", "text": "세팔론 시마리스 일일 연구 평판", "done": False},
        {"id": "weekly_archon", "type": "weekly", "text": "주간 집정관 토벌전 (아콘 샤드)", "done": False},
        {"id": "weekly_netracell", "type": "weekly", "text": "카비아 네트라셀 5회 클리어", "done": False},
        {"id": "weekly_eda", "type": "weekly", "text": "심층 아키메디아 (EDA) 3연전", "done": False},
        {"id": "weekly_iron_wake", "type": "weekly", "text": "아이언 웨이크 리벤 조각 교환", "done": False}
    ]
    ITEM_ALIASES = {
        'daily_sortie': ['출격', '소티', 'sortie'],
        'daily_sp_incursion': ['강길', '강철의 길', '침공', '에센스'],
        'daily_simaris': ['시마리스', '연구 평판'],
        'weekly_archon': ['집정관', '아콘', '샤드'],
        'weekly_netracell': ['네트라셀', '카비아'],
        'weekly_eda': ['아키메디아', '아르키메디아', '심층', '알키', 'eda'],
        'weekly_iron_wake': ['아이언 웨이크', '리벤 조각', '팔라디노']
    }
    QUESTION_WORDS = ('공략', '어떻게', '뭐야', '조건', '알려줘', '추천', '보상', '약점', '패턴')
    COMMAND_PREFIX = r'^(나\s*오늘|나\s*지금|방금|오늘|내일|이번\s*주|주간|일일)\s*'
    COMMAND_PARTICLE = r'(을|를|은|는|이|가|도)$'

    def __init__(self, data_file: Optional[str] = None, name_translator: Optional[Callable[[str], str]] = None):
        if data_file is None:
            self.data_file = get_user_data_path("user_checklist.json")
        else:
            self.data_file = data_file
        self.name_translator = name_translator
        self._last_good: Dict[str, Any] = {}
        self._ensure_checklist()

    def _ensure_checklist(self):
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        if not os.path.exists(self.data_file):
            self.save_checklist(copy.deepcopy(self.DEFAULT_CHECKLIST))

    def _read_items(self) -> List[Dict[str, Any]]:
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                items = json.load(f)
            if isinstance(items, list):
                return items
        except FileNotFoundError:
            return copy.deepcopy(self.DEFAULT_CHECKLIST)
        except (OSError, ValueError):
            pass
        # Unreadable file: keep it for recovery instead of silently replacing the user's list.
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        shutil.copy2(self.data_file, f"{self.data_file}.corrupt-{stamp}")
        items = copy.deepcopy(self.DEFAULT_CHECKLIST)
        self.save_checklist(items)
        return items

    def load_checklist(self) -> List[Dict[str, Any]]:
        items = self._read_items()

        now = datetime.now(timezone.utc)
        daily_key = now.strftime("%Y-%m-%d")
        iso = now.isocalendar()
        weekly_key = f"{iso[0]}-W{iso[1]:02d}"

        meta_file = f"{self.data_file}.meta.json"
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except (OSError, ValueError):
            meta = {"last_daily_key": None, "last_weekly_key": None}

        # Older versions stored the bare week number.
        if meta.get("last_weekly_key") == iso[1]:
            meta["last_weekly_key"] = weekly_key

        new_day = daily_key != meta.get("last_daily_key")
        new_week = weekly_key != meta.get("last_weekly_key")
        if not new_day and not new_week:
            return items

        for item in items:
            is_daily = item.get("type") == "daily" or "[일일]" in item.get("text", "")
            is_weekly = item.get("type") == "weekly" or "[주간]" in item.get("text", "")
            if (new_day and is_daily) or (new_week and is_weekly):
                item["done"] = False
        meta["last_daily_key"] = daily_key
        meta["last_weekly_key"] = weekly_key

        self.save_checklist(items)
        write_json_atomic(meta_file, meta)
        return items

    def save_checklist(self, items: List[Dict[str, Any]]):
        write_json_atomic(self.data_file, items)

    def toggle_item(self, item_id: str) -> List[Dict[str, Any]]:
        items = self.load_checklist()
        for it in items:
            if it.get("id") == item_id:
                it["done"] = not it.get("done", False)
                break
        self.save_checklist(items)
        return items

    def add_custom_item(self, text: str, item_type: str = "custom") -> List[Dict[str, Any]]:
        items = self.load_checklist()
        numbers = [int(m.group(1)) for m in (re.fullmatch(r"custom_(\d+)", str(i.get("id"))) for i in items) if m]
        new_id = f"custom_{max(numbers, default=0) + 1}"
        items.append({"id": new_id, "type": item_type, "text": text, "done": False})
        self.save_checklist(items)
        return items

    def delete_item(self, item_id: str) -> List[Dict[str, Any]]:
        items = self.load_checklist()
        items = [it for it in items if str(it.get("id")) != str(item_id)]
        self.save_checklist(items)
        return items

    def _translate(self, name: str) -> str:
        if not self.name_translator:
            return name
        try:
            return self.name_translator(name) or name
        except Exception:
            return name

    def _fetch_endpoint(self, endpoint: str) -> Any:
        response = requests.get(f"{self.API_URL}/{endpoint}", timeout=self.REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()

    def fetch_live_events(self) -> Dict[str, Any]:
        def fetch(endpoint: str) -> Any:
            try:
                return self._fetch_endpoint(endpoint)
            except Exception:
                return None

        with ThreadPoolExecutor(max_workers=len(self.ENDPOINTS)) as pool:
            responses = dict(zip(self.ENDPOINTS, pool.map(fetch, self.ENDPOINTS)))

        stale = []
        for endpoint, data in responses.items():
            if isinstance(data, dict):
                self._last_good[endpoint] = data
            else:
                stale.append(endpoint)

        events = parse_world_state(self._last_good, translate=self._translate)
        events["stale"] = [{"cetusCycle": "cetus", "duviriCycle": "duviri", "archonHunt": "archon", "voidTrader": "void_trader"}.get(e, e) for e in stale]
        return events

    @staticmethod
    def format_world_events(events: Dict[str, Any]) -> str:
        def card(*rows: str) -> str:
            body = "<br>".join(rows)
            return f"<div style='background-color: #141c2b; border: 1px solid #233147; padding: 10px; margin-bottom: 10px;'>{body}</div>"

        def text(value: Any) -> str:
            return html.escape(str(value))

        def with_time(label: str, time_left: Any) -> str:
            return f"{text(label)} ({text(time_left)})" if time_left else text(label)

        cetus = events.get("cetus", {})
        duviri = events.get("duviri", {})
        sortie = events.get("sortie", {})
        archon = events.get("archon", {})
        trader = events.get("void_trader", {})
        weapons = events.get("incarnon", {}).get("weapons") or []
        cetus_time = f"추정 {cetus.get('timeLeft')}" if cetus.get("estimated") else cetus.get("timeLeft")

        sortie_name = f"{sortie.get('boss', UNKNOWN)} · {sortie['faction']}" if sortie.get("faction") else sortie.get("boss", UNKNOWN)
        duviri_rows = [f"🌀 <b>두비리</b>: {text(duviri.get('state', UNKNOWN))} 나선"]
        if duviri.get("warframes"):
            duviri_rows.append(f"🤺 순회 워프레임: {text(', '.join(duviri['warframes']))}")

        cards = [
            card(f"🌕 <b>아이돌론</b>: {with_time(cetus.get('state', UNKNOWN), cetus_time)}", f"💡 {text(cetus.get('huntingTip', ''))}"),
            card(*duviri_rows),
            card(
                f"⚔️ <b>출격</b>: {with_time(sortie_name, sortie.get('timeLeft'))}",
                f"👑 <b>집정관</b>: {with_time(archon.get('boss', UNKNOWN), archon.get('timeLeft'))}",
            ),
            card(f"🔮 <b>이번 주 인카논</b>: {text(', '.join(weapons)) if weapons else UNKNOWN}"),
            card(
                f"📦 <b>바로 키티어</b>: {with_time(trader.get('status', UNKNOWN), trader.get('eta'))}",
                f"📍 {text(trader.get('location') or UNKNOWN)}",
            ),
        ]
        if events.get("stale"):
            cards.append("<div style='color: #94a3b8;'>⚠️ 일부 정보를 새로 받아오지 못해 마지막으로 받은 값을 표시합니다.</div>")
        return "".join(cards)

    def detect_todo_intent(self, text: str) -> Optional[str]:
        text_clean = text.strip()
        if '?' in text_clean or any(k in text_clean for k in ['어떻게', '뭐야', '공략', '약점', '알려줘', '추천']):
            return None

        todo_triggers = [
            r'(.+?)\s*(?:돌아야\s*겠[다어]|해야\s*겠[다어]|가야\s*겠[다어]|잡아야\s*겠[다어]|깨야\s*겠[다어]|파밍해야\s*겠[다어]|돌아야\s*지|해야\s*지|가야\s*지|잡아야\s*지|깨야\s*지|돌아야\s*돼|해야\s*돼|가야\s*돼|잡아야\s*돼|깨야\s*돼|사야\s*돼|파밍해야\s*돼|돌아야\s*해|해야\s*해|가야\s*해|잡아야\s*해|깨야\s*해|사야\s*해|파밍해야\s*해|돌거야|할거야|갈거야|잡을거야|깰거야|돌자|가자|갈래|할래|돌아야\s*하는데|해야\s*하는데)[.!]?$'
        ]
        for pattern in todo_triggers:
            m = re.search(pattern, text_clean)
            if m:
                extracted = m.group(1).strip()
                extracted = re.sub(r'^(나\s*오늘|나\s*지금|오늘|내일|주말에|이번\s*주|꼭|빨리|일단)\s*', '', extracted).strip()
                extracted = re.sub(r'(을|를|은|는|이|가|도)$', '', extracted).strip()
                if 2 <= len(extracted) <= 30:
                    return f'{extracted} 하기'
        return None

    def _clean_task_name(self, raw_name: str) -> str:
        name = re.sub(self.COMMAND_PREFIX, '', raw_name.strip()).strip()
        return re.sub(self.COMMAND_PARTICLE, '', name).strip()

    def _find_item(self, items: List[Dict[str, Any]], task_name: str) -> Optional[Dict[str, Any]]:
        # Too short to name anything ("일일 완료", "오늘 다 했어"): matching it would tick an arbitrary item.
        if len(task_name) < 2:
            return None
        lowered = task_name.lower()
        for item in items:
            text = item.get('text', '')
            if lowered in text.lower() or text.lower() in lowered:
                return item
            if any(alias in lowered for alias in self.ITEM_ALIASES.get(item.get('id', ''), [])):
                return item
        return None

    def process_chat_todo_command(self, user_text: str) -> Optional[Dict[str, Any]]:
        user_text = user_text.strip()

        # Questions and guide requests belong to the chat router.
        if '?' in user_text or any(keyword in user_text for keyword in self.QUESTION_WORDS):
            return None

        completion = re.search(r"(.+?)\s*(?:완료\s*했[어다음네]?|완료|다\s*했[어다음네]?|끝냈[어다음네]?|끝났[어다음네]?|클리어\s*했[어다음네]?|클리어|체크\s*해\s*줘?|체크해|다\s*돌았[어다음네]?|돌았[어다음네]?|깼[어다음네]?)[.!]?$", user_text, re.IGNORECASE)
        if completion:
            items = self.load_checklist()
            item = self._find_item(items, self._clean_task_name(completion.group(1)))
            if item is None:
                return None
            item['done'] = True
            self.save_checklist(items)
            return {
                "action": "COMPLETE",
                "task": item['text'],
                "message": f"✅ 오퍼레이터님! [{item['text']}] 숙제 완료 체크해 두었습니다! 수고하셨습니다!"
            }

        deletion = re.search(r"(.+?)\s*(?:숙제\s*삭제|목록에서\s*빼|할\s*일\s*지워|숙제\s*지워|삭제(?:해\s*줘?)?|지워\s*줘?)[.!]?$", user_text, re.IGNORECASE)
        if deletion:
            item = self._find_item(self.load_checklist(), self._clean_task_name(deletion.group(1)))
            if item is None:
                return None
            self.delete_item(item['id'])
            return {
                "action": "DELETE",
                "task": item['text'],
                "message": f"🗑️ 오퍼레이터님! [{item['text']}] 항목을 숙제 목록에서 삭제했습니다."
            }

        addition = re.search(r"(.+?)\s*(?:숙제\s*등록|숙제\s*추가|할\s*일\s*추가|할\s*일\s*등록)[.!]?$", user_text, re.IGNORECASE)
        if addition:
            task_name = self._clean_task_name(addition.group(1))
            if len(task_name) >= 2:
                self.add_custom_item(task_name)
                return {
                    "action": "ADD",
                    "task": task_name,
                    "message": f'📌 오퍼레이터님! [{task_name}] 항목을 새 숙제로 추가했습니다!'
                }

        return None

    def plan_todo_tool(self, tool_call: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Checks a model's tool call without changing anything.

        Returns the tool, the cleaned task name and, for complete/delete, the existing item it names.
        None when the call is malformed or names no item, so the caller can ask or fall back instead.
        """
        if not isinstance(tool_call, dict):
            return None
        tool = tool_call.get("tool")
        args = tool_call.get("args") or {}
        raw_task = args.get("task", "") if isinstance(args, dict) else ""
        if tool not in ("add_todo", "complete_todo", "delete_todo") or not isinstance(raw_task, str):
            return None
        task_name = self._clean_task_name(raw_task)
        if len(task_name) < 2:
            return None
        item = None
        if tool != "add_todo":
            item = self._find_item(self.load_checklist(), task_name)
            if item is None:
                return None
        return {"tool": tool, "task": task_name, "item": item}

    def execute_todo_tool(self, tool_call: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """[Step 2 연동] GBNF 문법으로 추출된 정형 도구 호출(JSON)을 안전하게 실행합니다."""
        plan = self.plan_todo_tool(tool_call)
        if plan is None:
            return None
        tool, task_name = plan["tool"], plan["task"]

        if tool == "add_todo":
            self.add_custom_item(task_name)
            return {
                "action": "ADD",
                "task": task_name,
                "message": f"📌 오퍼레이터님! [{task_name}] 항목을 새 숙제로 추가했습니다!",
            }
        elif tool == "complete_todo":
            items = self.load_checklist()
            item = self._find_item(items, task_name)
            if item is None:
                return None
            item["done"] = True
            self.save_checklist(items)
            return {
                "action": "COMPLETE",
                "task": item["text"],
                "message": f"✅ 오퍼레이터님! [{item['text']}] 숙제 완료 체크해 두었습니다! 수고하셨습니다!",
            }
        elif tool == "delete_todo":
            item = self._find_item(self.load_checklist(), task_name)
            if item is None:
                return None
            self.delete_item(item["id"])
            return {
                "action": "DELETE",
                "task": item["text"],
                "message": f"🗑️ 오퍼레이터님! [{item['text']}] 항목을 숙제 목록에서 삭제했습니다.",
            }
        return None

