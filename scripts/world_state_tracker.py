import os
import re
import json
import requests
from typing import Dict, Any, List, Optional
from scripts.path_config import get_path

class WorldStateTracker:
    API_URL = "https://api.warframestat.us/pc"
    DEFAULT_CHECKLIST = [
        {"id": "daily_sortie", "type": "daily", "text": "일일 출격 (Sortie) 3단계 클리어", "done": False},
        {"id": "daily_sp_incursion", "type": "daily", "text": "강철의 길 일일 침공 (에센스 5개)", "done": False},
        {"id": "daily_simaris", "type": "daily", "text": "세팔론 시마리스 일일 연구 평판", "done": False},
        {"id": "weekly_archon", "type": "weekly", "text": "주간 집정관 토벌전 (아콘 샤드)", "done": False},
        {"id": "weekly_netracell", "type": "weekly", "text": "카비아 네트라셀 5회 클리어", "done": False},
        {"id": "weekly_eda", "type": "weekly", "text": "심층 아키메디아 (EDA) 3연전", "done": False},
        {"id": "weekly_iron_wake", "type": "weekly", "text": "아이언 웨이크 리벤 조각 교환", "done": False}
    ]

    def __init__(self, data_file: str = "data/user_checklist.json"):
        self.data_file = get_path(data_file) if not os.path.isabs(data_file) else data_file
        self._ensure_checklist()

    def _ensure_checklist(self):
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        if not os.path.exists(self.data_file):
            self.save_checklist(self.DEFAULT_CHECKLIST)

    def load_checklist(self) -> List[Dict[str, Any]]:
            from datetime import datetime, timezone
            import json

            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    items = json.load(f)
            except Exception:
                items = self.DEFAULT_CHECKLIST

            # Determine current daily and weekly keys
            now = datetime.now(timezone.utc)
            current_daily_key = now.strftime("%Y-%m-%d")
            current_weekly_key = now.isocalendar()[1]

            # Load reset metadata
            meta_file = f"{self.data_file}.meta.json"
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception:
                meta = {"last_daily_key": None, "last_weekly_key": None}

            # Check and reset daily items
            if current_daily_key != meta.get("last_daily_key"):
                for item in items:
                    if item.get("type") == "daily" or "[일일]" in item.get("text", ""):
                        item["done"] = False
                meta["last_daily_key"] = current_daily_key

            # Check and reset weekly items
            if current_weekly_key != meta.get("last_weekly_key"):
                for item in items:
                    if item.get("type") == "weekly" or "[주간]" in item.get("text", ""):
                        item["done"] = False
                meta["last_weekly_key"] = current_weekly_key

            # Save updated checklist and metadata
            self.save_checklist(items)
            with open(meta_file, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)

            return items

    def save_checklist(self, items: List[Dict[str, Any]]):
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)

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
        new_id = f"custom_{len(items)+1}"
        items.append({"id": new_id, "type": item_type, "text": text, "done": False})
        self.save_checklist(items)
        return items

    def delete_item(self, item_id: str) -> List[Dict[str, Any]]:
        items = self.load_checklist()
        items = [it for it in items if str(it.get("id")) != str(item_id)]
        self.save_checklist(items)
        return items

    def fetch_live_events(self) -> Dict[str, Any]:
        result = {
            "cetus": {"state": "로딩 중", "timeLeft": "0m", "isNight": False},
            "duviri": {"state": "로딩 중", "choice": ""},
            "sortie": {"boss": "출격 로딩 중", "faction": "", "timeLeft": ""},
            "archon": {"boss": "집정관 로딩 중", "timeLeft": ""},
            "void_trader": {"active": False, "location": "", "eta": ""},
            "incarnon": {"rotation": "로딩 중", "boss": "집정관"}
        }
    
        try:
            r = requests.get(f"{self.API_URL}/cetusCycle", timeout=2.5).json()
            is_night = r.get("isNight", False)
            result["cetus"] = {
                "state": "밤 (3랄 출현!)" if is_night else "낮 (평화)",
                "timeLeft": r.get("timeLeft", "0m"),
                "isNight": is_night
            }
        except Exception:
            pass

        try:
            r = requests.get(f"{self.API_URL}/duviriCycle", timeout=2.5).json()
            state_kr = {"sorrow": "슬픔", "fear": "공포", "joy": "기쁨", "anger": "분노", "envy": "질투"}.get(r.get("state", ""), r.get("state", "나선"))
            result["duviri"] = {
                "state": state_kr,
                "choice": r.get("choice", "")
            }
        except Exception:
            pass

        try:
            r = requests.get(f"{self.API_URL}/sortie", timeout=2.5).json()
            result["sortie"] = {
                "boss": r.get("boss", "출격 보스"),
                "faction": r.get("faction", "적군"),
                "timeLeft": r.get("eta", "남음")
            }
        except Exception:
            pass

        try:
            r = requests.get(f"{self.API_URL}/archonHunt", timeout=2.5).json()
            result["archon"] = {
                "boss": r.get("boss", "집정관"),
                "timeLeft": r.get("eta", "남음")
            }
        except Exception:
            pass

        try:
            r = requests.get(f"{self.API_URL}/voidTrader", timeout=2.5).json()
            result["void_trader"] = {
                "active": r.get("active", False),
                "location": r.get("location", ""),
                "eta": r.get("startString", "")
            }
        except Exception:
            pass

        # Compute deterministic weekly Incarnon rotation
        from datetime import datetime
        now = datetime.utcnow()
        week_number = now.isocalendar()[1]
        week_cycle = ["A", "B", "C", "D", "E", "F", "G", "H"]
        week_index = (week_number - 1) % 8
        week_label = week_cycle[week_index]

        incarnon_rotation = {
            "A": ["브래튼", "래트론", "스카나", "파리스", "쿠나이"],
            "B": ["보어", "감마코어", "앙스트럼", "고르곤", "안쿠"],
            "C": ["보", "래트론", "퓨리스", "퓨랙스", "스트런"],
            "D": ["렉스", "마기스타", "볼터", "브롱코", "세라믹 대거"],
            "E": ["토리드", "듀얼 톡소시스트", "듀얼 이코르", "마이터", "아토모스"],
            "F": ["아클락", "버스튼", "바스토", "나미 솔로", "소마"],
            "G": ["제이락", "시비어", "드레드", "디스페어", "헤이트"],
            "H": ["데라", "세스트라", "사이바리스", "오키나", "시카루스"]
        }

        result["incarnon"] = {
            "rotation": week_label,
            "boss": incarnon_rotation[week_label][0]  # Assuming the first boss is the main one
        }

        return result

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

    def process_chat_todo_command(self, user_text: str) -> Optional[Dict[str, Any]]:
        user_text = user_text.strip()
    
        # Intercept questions or guide requests
        if '?' in user_text or any(keyword in user_text for keyword in ('공략', '어떻게', '뭐야', '조건', '알려줘', '추천', '보상', '약점', '패턴')):
            return None
    
        items = self.load_checklist()
    
        alias_map = {
            'daily_sortie': ['출격', '소티', 'sortie'],
            'daily_sp_incursion': ['강길', '강철의 길', '침공', '에센스'],
            'daily_simaris': ['시마리스', '연구 평판'],
            'weekly_archon': ['집정관', '아콘', '샤드'],
            'weekly_netracell': ['네트라셀', '카비아'],
            'weekly_eda': ['아키메디아', '아르키메디아', '심층', '알키', 'eda'],
            'weekly_iron_wake': ['아이언 웨이크', '리벤 조각', '팔라디노']
        }
    
        # Completion patterns
        completion_patterns = [
            r"(.+?)\s*(?:완료\s*했[어다음네]?|완료|다\s*했[어다음네]?|끝냈[어다음네]?|끝났[어다음네]?|클리어\s*했[어다음네]?|클리어|체크\s*해\s*줘?|체크해|다\s*돌았[어다음네]?|돌았[어다음네]?|�[어다음네]?)[.!]?$"
        ]
        for pattern in completion_patterns:
            m = re.search(pattern, user_text, re.IGNORECASE)
            if m:
                task_name = m.group(1).strip()
                task_name = re.sub(r'^(나\s*오늘|나\s*지금|방금|오늘|내일|이번\s*주|주간|일일)\s*', '', task_name).strip()
                task_name = re.sub(r'(을|를|은|는|이|가|도)$', '', task_name).strip()
                for item in items:
                    if (task_name in item['text'] or item['text'] in task_name or
                        any(a in task_name.lower() for a in alias_map.get(item.get('id', ''), [])) or
                        any(a in task_name.lower() for a in [str(item.get('id', '')).lower(), str(item.get('type', '')).lower()])):
                        item['done'] = True
                        self.save_checklist(items)
                        t_txt = item['text']
                        return {
                            "action": "COMPLETE",
                            "task": t_txt,
                            "message": f'✅ 오퍼레이터님! [{t_txt}] 숙제 완료 체크해 두었습니다! 수고하셨습니다!'
                        }
                return None
    
        # Deletion patterns
        deletion_patterns = [
            r"(.+?)\s*(?:숙제\s*삭제|목록에서\s*빼|할\s*일\s*지워|숙제\s*지워)[.!]?$"
        ]
        for pattern in deletion_patterns:
            m = re.search(pattern, user_text, re.IGNORECASE)
            if m:
                task_name = m.group(1).strip()
                task_name = re.sub(r'^(나\s*오늘|나\s*지금|방금|오늘|내일|이번\s*주|주간|일일)\s*', '', task_name).strip()
                task_name = re.sub(r'(을|를|은|는|이|가|도)$', '', task_name).strip()
                for item in items:
                    if (task_name in item['text'] or item['text'] in task_name or
                        any(a in task_name.lower() for a in alias_map.get(item.get('id', ''), [])) or
                        any(a in task_name.lower() for a in [str(item.get('id', '')).lower(), str(item.get('type', '')).lower()])):
                        self.delete_item(item['id'])
                        t_txt = item['text']
                        return {
                            "action": "DELETE",
                            "task": t_txt,
                            "message": f'🗑️ 오퍼레이터님! [{t_txt}] 항목을 숙제 목록에서 삭제했습니다.'
                        }
                return None
    
        # Direct add patterns
        add_patterns = [
            r"(.+?)\s*(?:숙제\s*등록|숙제\s*추가|할\s*일\s*추가|할\s*일\s*등록)[.!]?$"
        ]
        for pattern in add_patterns:
            m = re.search(pattern, user_text, re.IGNORECASE)
            if m:
                task_name = m.group(1).strip()
                task_name = re.sub(r'^(나\s*오늘|나\s*지금|방금|오늘|내일|이번\s*주|주간|일일)\s*', '', task_name).strip()
                task_name = re.sub(r'(을|를|은|는|이|가|도)$', '', task_name).strip()
                if len(task_name) >= 2:
                    self.add_custom_item(task_name)
                    return {
                        "action": "ADD",
                        "task": task_name,
                        "message": f'📌 오퍼레이터님! [{task_name}] 항목을 새 숙제로 추가했습니다!'
                    }
    
        return None

