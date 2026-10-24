import re
from typing import Dict, Any, Optional, Tuple

class EmotionParser:
    TAG_REGEX = re.compile(r'\[(?:MOOD|EMOTION):([^\]]+)\]', re.IGNORECASE)

    VALID_MOODS = {
        "idle", "neutral", "happy", "glitch", "tactical",
        "worried", "proud", "sad", "angry", "thinking"
    }

    MOOD_ALIASES = {
        "기쁨": "happy", "행복": "happy", "웃음": "happy",
        "글리치": "glitch", "버그": "glitch", "광기": "glitch", "살벌": "glitch",
        "전술": "tactical", "분석": "tactical", "진지": "tactical",
        "걱정": "worried", "불안": "worried", "염려": "worried",
        "자랑": "proud", "뿌듯": "proud", "당당": "proud",
        "슬픔": "sad", "우울": "sad", "시무룩": "sad",
        "화남": "angry", "분노": "angry",
        "생각": "thinking", "고민": "thinking",
        "기본": "idle", "평온": "idle"
    }

    INTENSITY_MAP = {
        "1": 1, "low": 1, "약": 1, "small": 1,
        "2": 2, "medium": 2, "mid": 2, "중": 2, "normal": 2,
        "3": 3, "high": 3, "강": 3, "huge": 3, "max": 3
    }

    def __init__(self):
        pass

    def parse(self, text: str) -> Dict[str, Any]:
        if not text:
            return {
                "clean_text": "",
                "mood": "idle",
                "secondary_mood": None,
                "intensity": 1,
                "vfx": None,
                "raw_tag": None
            }

        match = self.TAG_REGEX.search(text)
        if match:
            raw_tag = match.group(0)
            tag_content = match.group(1).strip()
            clean_text = self.TAG_REGEX.sub('', text).strip()

            mood, secondary_mood, intensity, vfx = self._parse_tag_content(tag_content)
            return {
                "clean_text": clean_text,
                "mood": mood,
                "secondary_mood": secondary_mood,
                "intensity": intensity,
                "vfx": vfx,
                "raw_tag": raw_tag
            }
        else:
            return self.infer_emotion(text)

    def _parse_tag_content(self, tag_content: str) -> Tuple[str, Optional[str], int, Optional[str]]:
        mood = "idle"
        secondary_mood = None
        intensity = 2
        vfx = None

        # Check for comma separated parameters e.g. [MOOD:happy:3,vfx=blush]
        tokens = [t.strip() for t in tag_content.split(',') if t.strip()]
        primary_token = tokens[0] if tokens else "idle"

        # Check for mixed emotions e.g. angry+sad
        if '+' in primary_token:
            parts = primary_token.split('+', 1)
            primary_token = parts[0].strip()
            sec_candidate = parts[1].strip().lower()
            secondary_mood = self.MOOD_ALIASES.get(sec_candidate, sec_candidate)

        # Check for intensity e.g. happy:3
        if ':' in primary_token:
            m_part, i_part = primary_token.split(':', 1)
            primary_token = m_part.strip()
            intensity = self.INTENSITY_MAP.get(i_part.strip().lower(), 2)

        norm_mood = primary_token.lower()
        mood = self.MOOD_ALIASES.get(norm_mood, norm_mood)
        if mood not in self.VALID_MOODS:
            mood = "happy" if "happy" in mood else "idle"

        # Process trailing parameters e.g. vfx=blush, intensity=3
        for extra in tokens[1:]:
            if '=' in extra:
                k, v = extra.split('=', 1)
                k, v = k.strip().lower(), v.strip().lower()
                if k == "vfx":
                    vfx = v
                elif k == "intensity":
                    intensity = self.INTENSITY_MAP.get(v, 2)
            else:
                extra_clean = extra.lower()
                if extra_clean in self.INTENSITY_MAP:
                    intensity = self.INTENSITY_MAP[extra_clean]
                elif extra_clean in ["blush", "sweat", "tears", "sparks", "glitch", "hearts"]:
                    vfx = extra_clean
                elif extra_clean in self.VALID_MOODS or extra_clean in self.MOOD_ALIASES:
                    secondary_mood = self.MOOD_ALIASES.get(extra_clean, extra_clean)

        return mood, secondary_mood, intensity, vfx

    def infer_emotion(self, text: str) -> Dict[str, Any]:
        t_lower = text.lower()

        # Glitch / rage indicators
        if any(w in t_lower for w in ['찢어', '박살', '숨통', '살인', '초토화', '피로 물', '뼈를', '--', '부숴버']):
            return {"clean_text": text, "mood": "glitch", "secondary_mood": None, "intensity": 3, "vfx": "sparks", "raw_tag": None}

        # Worried / safety indicators
        if any(w in t_lower for w in ['조심', '안전', '무리', '다치', '위험', '병원', '건강', '푹 쉬', '체력']):
            return {"clean_text": text, "mood": "worried", "secondary_mood": None, "intensity": 2, "vfx": "sweat", "raw_tag": None}

        # Proud / victory indicators
        if any(w in t_lower for w in ['완벽', '승리', '대단', '자랑', '해냈', '영광', '성공']):
            return {"clean_text": text, "mood": "proud", "secondary_mood": None, "intensity": 2, "vfx": None, "raw_tag": None}

        # Tactical / analysis indicators
        if any(w in t_lower for w in ['분석', '데이터', '보고', '약점', '속성', '모딩', '통계', '최적화', '전술']):
            return {"clean_text": text, "mood": "tactical", "secondary_mood": None, "intensity": 2, "vfx": None, "raw_tag": None}

        # Sad / apologetic indicators
        if any(w in t_lower for w in ['실패', '아쉽', '슬프', 'ㅠㅠ', 'ㅜㅜ', '죄송', '미안', '사과']):
            return {"clean_text": text, "mood": "sad", "secondary_mood": None, "intensity": 2, "vfx": "tears", "raw_tag": None}

        # Happy / cheerful indicators
        if any(w in t_lower for w in ['감사', '좋아', '반갑', '안녕', '응원', '최고', '환영', '!']):
            return {"clean_text": text, "mood": "happy", "secondary_mood": None, "intensity": 2, "vfx": None, "raw_tag": None}

        return {"clean_text": text, "mood": "idle", "secondary_mood": None, "intensity": 1, "vfx": None, "raw_tag": None}
