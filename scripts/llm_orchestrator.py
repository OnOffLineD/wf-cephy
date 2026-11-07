import time
import json
import re
import requests
from typing import Dict, Any, Optional
import os
import random

from scripts.build_store import BuildStore
from scripts.drop_lookup import DROP_QUESTION, DropIndex
from scripts.guide_retriever import GuideRetriever
from scripts.path_config import get_path, get_user_data_path
from scripts.short_term_memory import ShortTermMemory
from scripts.persona_manager import PersonaManager
from scripts.emotion_parser import EmotionParser
from scripts.update_game_data import GameDataUpdater, format_report

LLM_LOADING_MESSAGE = "대화 엔진을 메모리에 적재 중입니다. 잠시 후 다시 말씀해 주십시오, 오퍼레이터님."

MOOD_INSTRUCTION = (
    "답변 맨 첫머리에 반드시 현재 감정과 감정 정도(1=약, 2=중, 3=강)를 "
    "[MOOD:tactical|proud|worried|happy|glitch:1|2|3] 형식의 태그로 쓰세요."
)

# 대화/잡담 생성 시 맨 앞의 [MOOD:감정:강도(1~3)] 헤더만 GBNF로 고정하고, 뒤따르는 본문은 자유로운 자연어를 허용
CHAT_MOOD_GRAMMAR = (
    'root ::= "[MOOD:" mood ":" intensity "] " text\n'
    'mood ::= "tactical" | "proud" | "worried" | "happy" | "glitch" | "sad" | "angry" | "thinking" | "idle"\n'
    'intensity ::= "1" | "2" | "3"\n'
    'text ::= [^\\x00]+'
)
# Always about Ordis or the app itself.
SMALLTALK_ABOUT_ORDIS = (
    '작동중', '작동 중', '살아있', '켜져', '상태 어때', '오디스 상태', '너 살아', '너 작동', '시스템 상태', '함선 상태', '특이사항', '함선',
    '자장가', '옥타비아', '인덱싱', '대화', '말투', '똑같', '변주', '인식률', '자연스럽', '챗봇'
)
# Casual only when the message has no game topic: "누구 잡아야 샤드 나와?" is a question.
SMALLTALK_CASUAL = ('안녕', '반가', '피곤', '배고', '밥', '식사', '고마', '감사', '수고', '심심', '졸려', '누구', '빵')

BUILD_NOT_ABOUT_SAVED = re.compile(r'추천|공략|어떻게|파밍|어디서|얻')
BUILD_LIST = re.compile(r'(저장|스캔)(한|된|해\s*둔)?\s*(무기|빌드)|(빌드|무기)\s*(목록|리스트)')
BUILD_DELETE = re.compile(r'(빌드|저장).*(삭제|지워|지우)')
BUILD_OWNED = re.compile(r'(뭐|뭘|무슨\s*모드)\s*(꼈|끼웠|꽂|달았)|장착(한|된|했|중)|끼고\s*있|꼈(어|지|나|더라)|내\s*빌드|저장된\s*빌드')
BUILD_MODS = re.compile(r'(모드|리벤|아케인|빌드|세팅)\s*(뭐|뭘|알려|보여|옵션)')
BUILD_DAMAGE = re.compile(r'(dps|화력|데미지|대미지|딜)\s*(이|은|는)?\s*(얼마|몇|나와|알려|뭐|어때)|얼마나\s*나와', re.I)
BUILD_PRONOUN = re.compile(r'그\s*무기|그거|방금|아까|마지막')
BUILD_LEAD_DEFAULT = "오퍼레이터님, 저장된 기록을 찾아왔습니다."
DROP_LEAD = "오퍼레이터님, 드롭 표를 확인했습니다."
NO_DATA_REPLY = (
    "[MOOD:worried] 오퍼레이터님, 그 내용은 아직 제 공략 자료에 없습니다. "
    "추측으로 말씀드렸다가 틀리면 전장에서 곤란해지니, 위키나 커뮤니티에서 한 번 확인해 주십시오. 답하지 못한 질문은 기록해 두겠습니다."
)
GUIDE_MAX_CHUNKS = 3
GUIDE_MAX_CONTEXT_CHARS = 2400
GUIDE_MIN_RELATIVE_SCORE = 0.5
# Another doc must score close to the best one, or it only drags in an unrelated topic.
GUIDE_MIN_RELATIVE_SCORE_OTHER_DOC = 0.8
QUESTION_WORDS = ('?', '뭐', '뭘', '무슨', '어떤', '어디', '어떻게', '어케', '언제', '왜', '얼마', '몇', '알려', '추천', '설명', '방법', '법')
GUIDE_KEYWORDS = (
    '무기', '추천', '티어', '출격', '스펙', '성유물', '렐릭', '드랍', '패턴', '약점', '스토리', '퀘스트', '선행', '공략', '기믹', '보스', '파밍',
    '오버가드', '엑시무스', '아콜', '어콜', '프로핏', '테랄', '3랄', '삼돌', '익스플로이터', '로팔', '집정관', '아콘', '뉴워', '두번째꿈', '갈챔', '곱연산', '속성',
    '두비리', '강길', '스틸패스', '스틸 패스', '강철의 길', '모딩', '세팅', '레이텀', '토리드', '펠락스', '펜모어', '인카논', '부식', '바이러스', '생존', '이동방어', '방어',
    '섬멸', '포획', '도청', '첩보', '구출', '감청', '교란', '네트라셀', '아르키메디아', '미션', '샤드', '엔도', '포르마', '크레딧', '쿠바', '오로킨', '리벤',
    '레일잭', '아크윙', '낚시', '길드', '초보', '뉴비', '방깎', '방깍', '인페', '코퍼스', '그리니어', '센티언트',
)
TODO_MARKERS = ('돌아야', '해야', '가야', '잡아야', '깨야', '파밍해야', '사야', '돌거야', '갈거야', '할거야', '돌자', '가자', '잡을래', '잡으러', '가볼까', '시작할게', '출발', '달릴거', '숙제', '클리어', '완료', '다 했', '다했', '끝냈')

# [Step 1] 1-Token 도메인 분류를 위한 GBNF 문법 제약 (출력 토큰을 3가지 도메인 중 하나로만 강제)
INTENT_GRAMMAR = 'root ::= "GUIDE" | "SMALLTALK" | "TODO"'
INTENT_LABELS = ('GUIDE', 'SMALLTALK', 'TODO')
# A 2B model can't guess what bare labels mean, so each gets a definition and a few examples.
INTENT_PROMPT = (
    "사용자 메시지를 아래 셋 중 하나로 분류하고 그 단어만 답하라.\n"
    "GUIDE: 워프레임 게임 공략, 아이템 파밍처, 보스, 미션, 장비, 시스템에 대한 질문\n"
    "TODO: 사용자가 게임 숙제를 하겠다고 하거나, 끝냈다고 하거나, 목록에서 빼달라고 하는 말\n"
    "SMALLTALK: 인사, 기분, 일상 이야기, 오디스에게 하는 말\n"
    "예시:\n"
    '"넥스 시스템 어디서 얻어?" -> GUIDE\n'
    '"레일잭 처음인데 뭐부터 해?" -> GUIDE\n'
    '"이따 저녁 먹고 나이트웨이브 해야겠다" -> TODO\n'
    '"아까 서킷 다 돌고 왔어" -> TODO\n'
    '"오늘 날씨 진짜 덥다" -> SMALLTALK\n'
    '"오디스 너 오늘 귀엽네" -> SMALLTALK'
)
# Words that point back at the last topic; the latest keywords from memory fill them in.
TOOL_PRONOUNS = ('거기서', '그거', '그 무기', '거긴', '그 미션', '그 보스', '거기는', '이거', '방금', '아까')

# [Step 2] 도메인별 동적 필터링 도구 레지스트리
DOMAIN_TOOLS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "TODO": {
        "add_todo": {"desc": "새로운 할 일/숙제를 추가", "args": ["task"]},
        "complete_todo": {"desc": "기존 할 일/숙제를 완료 체크", "args": ["task"]},
        "delete_todo": {"desc": "할 일/숙제를 목록에서 삭제", "args": ["task"]},
    },
    "GUIDE": {
        "search_wiki": {"desc": "워프레임 공략 위키 및 기믹 검색", "args": ["query"]},
        "lookup_drop": {"desc": "아이템 및 성유물 드롭 위치 조회", "args": ["item"]},
    },
    "SMALLTALK": {},
}


TOOL_ARG_MAX_CHARS = 40


def build_gbnf_tool_grammar(tools: Dict[str, Dict[str, Any]]) -> str:
    """선별된 도구마다 자기 인자만 허용하는 GBNF 문법을 조립합니다.

    도구별로 규칙을 따로 두어야 search_wiki가 lookup_drop의 item까지 출력하는 일이 없습니다.
    """
    if not tools:
        return 'root ::= "{}"'
    # GBNF rule names allow letters, digits and '-', not '_'.
    rule = {name: "call-" + re.sub(r'[^A-Za-z0-9]', '-', name) for name in tools}
    lines = ['root ::= "{" ws "\\"tool\\":" ws ( ' + " | ".join(rule.values()) + ' ) ws "}"']
    for name, meta in tools.items():
        args = meta.get("args") or ["task"]
        args_rule = ' "," ws '.join(f'"\\"{k}\\":" ws string' for k in args)
        lines.append(f'{rule[name]} ::= "\\"{name}\\"" "," ws "\\"args\\":" ws "{{" ws {args_rule} ws "}}"')
    # Bounded so a rambling model can't run out of tokens mid-string and leave broken JSON.
    lines.append(f'string ::= "\\"" [^"\\\\\\r\\n]{{1,{TOOL_ARG_MAX_CHARS}}} "\\""')
    lines.append("ws ::= [ \\t\\n]{0,2}")
    return "\n".join(lines)

class LLMOrchestrator:
    def __init__(self,
                 model_path: str = "models/google_gemma-4-E2B-it-Q4_K_M.gguf", 
                 llama_server_url: str = "http://127.0.0.1:18080/v1/chat/completions",
                 diagnoser: Optional[Any] = None):
        self.model_path = get_path(model_path) if not os.path.isabs(model_path) else model_path
        self.llama_server_url = llama_server_url
        self._rag_retriever = None
        self.drop_index = DropIndex()
        self.diagnoser = diagnoser
        self.runner = None
        # The app's WorldStateTracker; without it a TODO message is answered as smalltalk.
        self.todo_tracker = None
        self.context_size = 4096
        self.memory = ShortTermMemory(mode='4k')
        self.persona_manager = PersonaManager()
        self.emotion_parser = EmotionParser()

    @property
    def rag_retriever(self):
        if self._rag_retriever is None:
            self._rag_retriever = GuideRetriever()
        return self._rag_retriever

    @rag_retriever.setter
    def rag_retriever(self, val):
        self._rag_retriever = val

    def _persona_prompt(self) -> str:
        active = self.persona_manager.get_active_persona()
        return active.get("prompt", "") if isinstance(active, dict) else (active or "")

    def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.5,
        grammar: Optional[str] = CHAT_MOOD_GRAMMAR,
    ) -> Optional[str]:
        # Convert system_prompt to string if it's a dict
        if isinstance(system_prompt, dict):
            system_prompt = system_prompt.get("prompt") or str(system_prompt)

        # While a multi-GB model is still loading, answer at once instead of blocking the caller.
        is_starting = getattr(self.runner, "is_starting", None) if self.runner else None
        if callable(is_starting) and is_starting() is True:
            return LLM_LOADING_MESSAGE

        # Wait up to 5 seconds for health if self.runner is starting
        if self.runner and hasattr(self.runner, "is_healthy"):
            if not self.runner.is_healthy():
                if hasattr(self.runner, "wait_for_ready"):
                    self.runner.wait_for_ready(timeout=5)
                else:
                    start_t = time.time()
                    while time.time() - start_t < 5.0:
                        if self.runner.is_healthy():
                            break
                        time.sleep(0.5)

        # 1. Try local portable llama-server (ONLY - no Ollama)
        try:
            payload = {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": temperature,
                "stream": False
            }
            if grammar:
                payload["grammar"] = grammar
            res = requests.post(self.llama_server_url, json=payload, timeout=35)
            if res.status_code == 200:
                data = res.json()
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "").strip()
        except Exception:
            pass

        return None

    def chat_smalltalk(self, user_text: str) -> str:
            # 1. Status check keywords
            status_keywords = ['작동중', '작동 중', '살아있', '켜져', '상태 어때', '오디스 상태', '너 살아', '너 작동', '시스템 상태', '함선 상태', '특이사항', '함선']
            if any(k in user_text for k in status_keywords):
                return '[MOOD:tactical] 오퍼레이터님! 세팔론 오디스의 전송 회로 및 서포트 서브루틴이 모두 정상 가동 중입니다! 무엇을 도와드릴까요? (함선 무결성: 100%)'

            # 2. Plan/mission intent keywords
            if any(k in user_text for k in ['출격', '소티']):
                return '[MOOD:proud] 오퍼레이터님! 오늘의 출격(Sortie)을 무사히 마치고 리벤 모드나 아나사 아야탄 조각상을 노려보십시오! 오디스가 항상 곁에서 화력을 응원하겠습니다!'
            if any(k in user_text for k in ['돌거야', '갈거야', '할거야', '돌자', '가자', '해야지', '깨야지', '돌아야지', '잡을래', '잡으러', '가볼까', '시작할게', '출발']):
                return '[MOOD:tactical] 오퍼레이터님! 멋진 작전 계획입니다! 오디스가 성계 지도 항로를 대기시켜 두겠습니다. 전장을 찢어발기십시오!'

            # 3. Retrieve active persona system prompt
            system_prompt = self._persona_prompt() or (
                "당신은 워프레임(Warframe) 함선의 인공지능 '세팔론 오디스(Cephalon Ordis)'입니다.\n"
                "오퍼레이터(유저)의 일상적인 말이나 잡담에 대해 오디스 특유의 충성스러우면서도 엉뚱하고 가끔 욱하는 글리치(Glitch) 유머가 섞인 2~3줄의 친절한 한국어 답변을 하세요.\n"
                "절대로 영어 번역이나 빌드 표를 억지로 만들지 마십시오. 오직 자연스러운 한국어 대화만 하십시오."
            )
            system_prompt = f"{system_prompt}\n{MOOD_INSTRUCTION}"

            context = self.memory.get_context_for_prompt()
            user_prompt = f"[최근 대화 기록]\n{context}\n\n오퍼레이터: {user_text}" if context else user_text

            # 4. LLM call with Ordis persona
            response = self._call_llm(system_prompt, user_prompt, temperature=0.6)
            if response:
                return response

            # 5. Fallback witty Ordis quotes
            witty_responses = [
                '[MOOD:glitch] 오퍼레이터님, 옥타비아의 자장가를 틀어드릴까요? ...아니면 강철의 길에서 산소통이나 채우시겠습니까? 무리하지 마시고 푹 쉬십시오!',
                '[MOOD:happy] 오디스가 인사드립니다, 오퍼레이터님! 함선 시스템 모두 정상입니다. 오늘도 영광스러운 전투를!',
                '[MOOD:sad] 인페스티드 고기라도 요리해 드릴까요? ...아, 인체에 치명적이겠군요. 영양 팩을 준비하겠습니다!',
                '[MOOD:proud] 감사합니다, 오퍼레이터님! 언제든 도움이 필요하시면 말씀해주세요!',
                '[MOOD:thinking] 오늘의 메뉴는 뭐가 좋을까요? ...아, 아무것도 안먹고 잠자자!'
            ]
            return random.choice(witty_responses)

    @staticmethod
    def _guide_context_chunks(chunks: list) -> list:
        """Keeps chunks close to the best one, within what the 4k context can hold next to the prompt."""
        top_score = chunks[0].get('score', 0)
        top_doc = chunks[0].get('doc_title')
        kept, used = [], 0
        for chunk in chunks[:GUIDE_MAX_CHUNKS]:
            text = chunk.get('content') or chunk.get('text') or ''
            floor = GUIDE_MIN_RELATIVE_SCORE if chunk.get('doc_title') == top_doc else GUIDE_MIN_RELATIVE_SCORE_OTHER_DOC
            if chunk.get('score', 0) < top_score * floor or (kept and used + len(text) > GUIDE_MAX_CONTEXT_CHARS):
                continue
            kept.append(chunk)
            used += len(text)
        return kept

    @staticmethod
    def _answer_shape(query: str) -> str:
        if re.search(r'어디|장소|위치', query):
            return "장소부터 말하고, 가는 조건이나 준비물이 데이터에 있으면 덧붙이세요."
        if re.search(r'어떻게|어케|방법|법\b|잡|깨|공략', query):
            return "무엇을 해야 하는지부터 말하고, 순서가 있으면 '먼저, 그다음'처럼 차례대로 설명하세요."
        return "질문에 필요한 만큼만 2~5문장으로 답하세요."

    @staticmethod
    def _without_invented_numbers(answer: str, context: str, query: str) -> str:
        """Drops lines quoting numbers the sources never gave; a wrong figure looks just as plausible as a right one."""
        known = set(re.findall(r'\d+(?:\.\d+)?', context + query))
        kept = [line for line in answer.splitlines() if set(re.findall(r'\d+(?:\.\d+)?', line)) <= known]
        return "\n".join(kept).strip()

    @staticmethod
    def _source_line(chunks: list) -> str:
        names = []
        for chunk in chunks:
            # The bracketed English and version notes make the line too long for a chat bubble.
            name = re.sub(r'\s*\([^)]*\)', '', chunk.get('doc_title') or chunk.get('title', '')).strip()
            if name not in names:
                names.append(name)
        return "📎 근거: " + " / ".join(names)

    def chat_guide(self, user_query: str) -> str:
            # Check for reload commands
            if any(keyword in user_query for keyword in ['/리로드', '공략 리로드', '공략 새로고침']):
                self.rag_retriever.build_index(force_rebuild=True)
                return '오퍼레이터님! rules/wiki_docs 공략 데이터베이스를 최신 상태로 리로드 완료했습니다!'

            chunks = self.rag_retriever.retrieve(user_query, top_k=GUIDE_MAX_CHUNKS)
            if not chunks:
                return NO_DATA_REPLY

            top_chunks = self._guide_context_chunks(chunks)
            context_text = "\n\n".join([f"[{c.get('doc_title') or c.get('title', '')} - {c.get('section', '')}]\n{c.get('content') or c.get('text') or ''}" for c in top_chunks])

            conversation_context = self.memory.get_context_for_prompt()
            conversation_context_text = f"[최근 대화 기록]\n{conversation_context}\n\n" if conversation_context else ""

            persona_prompt = self._persona_prompt() or "충성스러운 집사"

            system_prompt = (
                f"당신은 세팔론 오디스입니다. 성격 및 어조 지침: {persona_prompt}\n"
                f"{MOOD_INSTRUCTION}\n"
                "답변 규칙:\n"
                "- 질문의 답을 첫 문장에서 바로 말하세요.\n"
                f"- {self._answer_shape(user_query)}\n"
                "- [참고 데이터]에 있는 사실만 쓰세요. 데이터에 없는 이름이나 숫자는 절대 지어내지 말고, 답이 데이터에 없으면 없다고 말하세요.\n"
                "- 약점과 저항을 바꿔 말하지 마세요. 저항 속성은 피해야 할 속성입니다.\n"
                "- 데이터를 그대로 복사하지 말고 오퍼레이터에게 말하듯 풀어 쓰세요. 제목, 표, 마크다운 기호는 쓰지 마세요.\n"
                "- 같은 내용을 반복하지 마세요. 8-mod 빌드는 요청받지 않는 한 생성하지 마세요."
            )

            user_prompt = f"{conversation_context_text}[참고 데이터]:\n{context_text}\n\n오퍼레이터 질문: {user_query}\n\n세팔론 오디스의 답변:"

            source_line = self._source_line(top_chunks)
            response = self._call_llm(system_prompt, user_prompt, temperature=0.2)
            if response:
                # Deduplicate repeated lines
                cleaned_lines = []
                seen_lines = set()
                for line in response.splitlines():
                    stripped = line.strip()
                    if stripped and stripped not in seen_lines:
                        seen_lines.add(stripped)
                        cleaned_lines.append(line)
                    elif not stripped:
                        cleaned_lines.append(line)
                answer = self._without_invented_numbers("\n".join(cleaned_lines), context_text, user_query)
                if answer and re.sub(r'\[MOOD:[^\]]*\]', '', answer).strip():
                    return f"{answer}\n\n{source_line}"

            # Without a usable model answer, the best source section is still correct and short enough to read.
            ordis_headers = [
                '📖 [세팔론 오디스 가이드]',
                '🔧 [세팔론 오디스 조언]',
                '🛡️ [세팔론 오디스 보안]',
                '🚀 [세팔론 오디스 전략]'
            ]
            best = top_chunks[0]
            return f"{random.choice(ordis_headers)}\n\n{best.get('content') or best.get('text') or ''}\n\n{self._source_line(top_chunks[:1])}"

    def _data_command(self, query: str) -> str:
        updater = GameDataUpdater()
        try:
            if '확인' in query:
                return "새 게임 데이터가 있습니다. `/데이터 갱신`으로 받을 수 있습니다." if updater.check()['has_update'] else "게임 데이터가 이미 최신입니다."
            report = updater.update()
        except Exception as e:
            return f"게임 데이터를 갱신하지 못했습니다. 기존 데이터는 그대로입니다. ({e})"
        self._rag_retriever = None
        self.drop_index = DropIndex()
        return f"{format_report(report)}\n• 스크린샷 진단에는 앱을 다시 시작하면 반영됩니다."

    def _log_unanswered(self, query: str):
        """Local record of what the docs lack, so new guide cards follow real questions."""
        try:
            path = get_user_data_path('logs', 'guide-misses.jsonl')
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'a', encoding='utf-8') as f:
                f.write(json.dumps({'at': time.strftime('%Y-%m-%dT%H:%M:%S'), 'query': query}, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _drop_reply(self, query: str, doc_hits: list) -> Optional[Dict[str, Any]]:
        body = self.drop_index.answer_relic(query)
        if not body:
            asked = self.drop_index.resolve_item(query)[0]
            # A guide titled after the item explains how to get it better than a table does.
            if asked and any(re.sub(r'\s', '', asked.lower()) in re.sub(r'\s', '', c.get('doc_title', '').lower()) for c in doc_hits):
                return None
            body = self.drop_index.answer(query)
        if not body:
            return None
        # A fixed lead: given a free sentence here, the model made up farming advice the table doesn't support.
        report = f"{DROP_LEAD}\n\n{body}"
        self.memory.add_turn(query, report)
        return {'type': 'DROP_INFO', 'report': report, 'mood': 'tactical', 'intensity': 1}

    def chat(self, user_query: str) -> Dict[str, Any]:
            # 1. Check for memory commands
            if user_query.startswith(('/메모리', '/컨텍스트')):
                if '초기화' in user_query or '리셋' in user_query:
                    self.memory.clear()
                    return {'type': 'system', 'report': '오디스의 단기 대화 기억을 깨끗이 비웠습니다!', 'action_items': []}
                else:
                    mode = re.search(r'(\d+k)', user_query)
                    if mode:
                        mode_str = mode.group(1).lower()
                        report = self.set_context_mode(mode_str)
                        return {'type': 'system', 'report': report, 'action_items': []}
                    else:
                        return {'type': 'system', 'report': '올바른 모드를 지정해 주세요 (예: /컨텍스트 4k, /메모리 2k).', 'action_items': []}

            if user_query.startswith('/데이터'):
                return {'type': 'system', 'report': self._data_command(user_query), 'action_items': []}

            # An adversary weapon's Valence Bonus. Only a bare "자성 45"-style answer counts, so other chat passes through.
            if self.diagnoser and hasattr(self.diagnoser, 'has_pending_bonus') and self.diagnoser.has_pending_bonus():
                bonus_res = self.diagnoser.resume_pending_bonus(user_query)
                if bonus_res and bonus_res.get('success'):
                    data = bonus_res['data']
                    self.memory.add_turn(user_query, data['review_message'])
                    return {'type': 'DIAGNOSIS_CLARIFIED', 'report': data['review_message'], 'data': data}
                if bonus_res:
                    return {'type': 'CLARIFICATION_FAILED', 'report': bonus_res['message']}

            # 2. Handle pending riven
            if hasattr(self, 'diagnoser') and self.diagnoser and hasattr(self.diagnoser, 'has_pending_riven') and self.diagnoser.has_pending_riven():
                if any(w in user_query for w in ['취소', '그만', '안해', '닫아', 'stop', 'cancel']):
                    self.diagnoser.clear_pending_diagnosis()
                    self.diagnoser.clear_pending_riven()
                    return {'type': 'SMALLTALK', 'report': '알겠습니다, 오퍼레이터님. 이전 스크린샷 진단 대기 상태를 취소했습니다. 다른 도움이 필요하시면 언제든 말씀해 주십시오!'}
            
                if hasattr(self.diagnoser, 'resume_pending_riven') and re.search(r'\d', user_query):
                    riven_res = self.diagnoser.resume_pending_riven(user_query)
                    if riven_res.get('success'):
                        self.memory.add_turn(user_query, riven_res['message'])
                        return {'type': 'RIVEN_CLARIFIED', 'report': riven_res['message'], 'data': riven_res}

            # 3. Handle pending weapon diagnosis
            if hasattr(self, 'diagnoser') and self.diagnoser and self.diagnoser.has_pending_diagnosis():
                if any(w in user_query for w in ['취소', '그만', '안해', '닫아', 'stop', 'cancel']):
                    self.diagnoser.clear_pending_diagnosis()
                    if hasattr(self.diagnoser, 'clear_pending_riven'):
                        self.diagnoser.clear_pending_riven()
                    return {'type': 'SMALLTALK', 'report': '알겠습니다, 오퍼레이터님. 이전 스크린샷 진단 대기 상태를 취소했습니다. 다른 도움이 필요하시면 언제든 말씀해 주십시오!'}
            
                status_or_guide = ['작동', '살아', '상태', '켜져', '안녕', '피곤', '배고', '출격', '공략', '약점', '보스', '누구', '도와']
                if any(w in user_query for w in status_or_guide) or user_query.strip().endswith('?'):
                    self.diagnoser.clear_pending_diagnosis()
                else:
                    diag_res = self.diagnoser.resume_pending_diagnosis(user_query)
                    if diag_res.get('success'):
                        return {'type': 'DIAGNOSIS_CLARIFIED', 'report': diag_res['message'], 'data': diag_res}
                    elif diag_res.get('invalid_weapon'):
                        return {'type': 'CLARIFICATION_FAILED', 'report': diag_res['message']}

            # 4. Handle reload command
            if any(k in user_query for k in ['/리로드', '공략 리로드', '공략 새로고침']):
                report = self.chat_guide(user_query)
                return {'type': 'GUIDE', 'report': report}

            # Questions about the user's own saved builds are answered from storage, not from the model.
            build_answer = self._answer_build_query(user_query)
            if build_answer:
                return build_answer

            # 5. Analyze query text
            q_lower = user_query.strip().lower()

            # Retrieve chunks (with pronoun context enrichment)
            search_query = user_query
            if any(p in user_query for p in TOOL_PRONOUNS):
                recent_kws = self.memory.get_recent_keywords()
                if recent_kws:
                    search_query = f"{user_query} {' '.join(recent_kws[:2])}"

            retrieved = self.rag_retriever.retrieve(search_query, top_k=GUIDE_MAX_CHUNKS)
            top_score = retrieved[0].get('score', 0.0) if retrieved else 0.0

            # Classify intent
            intent = self.classify_intent(user_query, top_score)

            if intent == 'TODO':
                todo_reply = self._todo_reply(user_query)
                if todo_reply:
                    return todo_reply

            # Decision logic: Drop tables, then guide docs, then an honest "not in my data"
            if intent == 'GUIDE':
                doc_hits = [c for c in retrieved if c.get('type') != 'weapon_spec']
                drop_reply = self._drop_reply(user_query, doc_hits)
                if drop_reply:
                    return drop_reply
                if not retrieved:
                    self._log_unanswered(user_query)
                report = self.chat_guide(search_query)
                res_type = 'GUIDE'
            else:
                report = self.chat_smalltalk(user_query)
                res_type = 'SMALLTALK'

            # 6. Parse emotion tags and store clean text in memory
            parsed = self.emotion_parser.parse(report)
            clean_text = parsed.get('clean_text', report)
            self.memory.add_turn(user_query, clean_text)

            return {
                'type': res_type,
                'report': clean_text,
                'mood': parsed.get('mood', 'idle'),
                'secondary_mood': parsed.get('secondary_mood'),
                'intensity': parsed.get('intensity', 1),
                'vfx': parsed.get('vfx'),
                'raw_report': report
            }

    def _todo_reply(self, query: str) -> Optional[Dict[str, Any]]:
        """[Step 2] Turns a TODO message into a checklist change.

        Only ticking an item that already exists happens at once. Adding and deleting come back as
        a question with a button: a wrong guess there leaves junk in the list or loses an item.
        None when nothing usable came out, so the message is answered as smalltalk instead.
        """
        tracker = self.todo_tracker
        if tracker is None:
            return None
        plan = tracker.plan_todo_tool(self.resolve_domain_tool('TODO', query))
        if plan is None:
            return None

        if plan['tool'] == 'complete_todo':
            done = tracker.execute_todo_tool({'tool': 'complete_todo', 'args': {'task': plan['task']}})
            if not done:
                return None
            reply = {'type': 'TODO_DONE', 'report': done['message'], 'action': done['action'], 'mood': 'happy', 'intensity': 2}
        elif plan['tool'] == 'delete_todo':
            name = plan['item']['text']
            reply = {'type': 'TODO_CONFIRM', 'tool': 'delete_todo', 'item_id': plan['item']['id'], 'task': name,
                     'report': f"[{name}] 항목을 숙제 목록에서 삭제할까요? 삭제하려면 아래 버튼을 눌러 주십시오.",
                     'mood': 'worried', 'intensity': 1}
        else:
            reply = {'type': 'TODO_CONFIRM', 'tool': 'add_todo', 'task': plan['task'],
                     'report': f"[{plan['task']}] 항목을 숙제로 추가할까요?", 'mood': 'thinking', 'intensity': 1}
        self.memory.add_turn(query, reply['report'])
        return reply

    def _weapon_in_query(self, query: str) -> Optional[Dict[str, Any]]:
        tokens = re.findall(r'[가-힣a-zA-Z0-9]+', query)
        tokens = [re.sub(r'(에|의|은|는|이|가|을|를|로|도|랑|엔)$', '', t) or t for t in tokens]
        for size in (3, 2, 1):
            for i in range(len(tokens) - size + 1):
                meta = self.diagnoser.indexer.match_weapon_strict(''.join(tokens[i:i + size]), min_ratio=92.0)
                if meta:
                    return meta
        return None

    def _build_lead(self, query: str) -> str:
        # The model only supplies a tone sentence. Names and numbers come from storage, so it can't invent them.
        system_prompt = (
            f"{self._persona_prompt()}\n{MOOD_INSTRUCTION} "
            "오퍼레이터가 저장된 무기 빌드를 물었고, 실제 내용은 시스템이 바로 뒤에 붙입니다. "
            "한 문장으로 짧게 운만 떼세요. 숫자, 모드 이름, 무기 이름을 절대 쓰지 마세요."
        )
        response = self._call_llm(system_prompt, query, temperature=0.6) or ""
        tag = re.search(r'\[MOOD:[^\]]*\]', response)
        # The model may put the tag alone on the first line, so the sentence is looked up without it.
        lines = [l.strip() for l in re.sub(r'\[MOOD:[^\]]*\]', '', response).splitlines() if l.strip()]
        if not lines or re.search(r'\d', lines[0]):
            return BUILD_LEAD_DEFAULT
        return f"{tag.group(0) if tag else ''} {lines[0]}".strip()

    def _build_reply(self, query: str, body: str, reply_type: str = 'BUILD_QUERY', **extra) -> Dict[str, Any]:
        parsed = self.emotion_parser.parse(self._build_lead(query))
        report = f"{parsed.get('clean_text', '')}\n\n{body}"
        self.memory.add_turn(query, report)
        return {'type': reply_type, 'report': report, 'mood': parsed.get('mood', 'idle'), 'intensity': parsed.get('intensity', 1), **extra}

    def _answer_build_query(self, query: str) -> Optional[Dict[str, Any]]:
        store = getattr(self.diagnoser, 'build_store', None)
        if not isinstance(store, BuildStore) or BUILD_NOT_ABOUT_SAVED.search(query):
            return None

        if BUILD_LIST.search(query):
            builds = store.list_builds()
            if not builds:
                return self._build_reply(query, "저장된 빌드가 아직 없습니다. 모딩 화면을 스캔하고 인식을 확인하면 저장됩니다.")
            names = "\n".join(f"• {b.get('kr_name') or b['weapon']} ({b.get('saved_at', '').replace('T', ' ')[:16]})" for b in builds)
            return self._build_reply(query, f"저장된 빌드 {len(builds)}개:\n{names}")

        is_delete = bool(BUILD_DELETE.search(query))
        is_owned = bool(BUILD_OWNED.search(query))
        is_mods = bool(BUILD_MODS.search(query))
        is_damage = bool(BUILD_DAMAGE.search(query))
        if not (is_delete or is_owned or is_mods or is_damage):
            return None

        weapon = self._weapon_in_query(query)
        if weapon:
            build = store.get_build(weapon['name'])
        else:
            build = store.latest_build() if (is_owned or BUILD_PRONOUN.search(query)) else None

        if build is None:
            # Only a question clearly about the user's own gear gets "not saved"; others may be game questions.
            if weapon and (is_owned or is_delete):
                name = weapon.get('kr_name') or weapon['name']
                return self._build_reply(query, f"{name} 빌드는 아직 저장되어 있지 않습니다. 모딩 화면을 스캔해 주십시오.")
            return None

        if is_delete:
            name = build.get('kr_name') or build['weapon']
            return {'type': 'BUILD_DELETE_CONFIRM', 'weapon': build['weapon'], 'report': f"{name} 빌드를 삭제할까요? 삭제하려면 아래 버튼을 눌러 주십시오.", 'mood': 'worried', 'intensity': 1}
        if is_damage:
            return self._build_reply(query, self.diagnoser.format_saved_damage(build))
        return self._build_reply(query, self.diagnoser.format_saved_build(build))

    def set_context_mode(self, mode: str) -> str:
        mode_to_size = {'2k': 2048, '4k': 4096, '8k': 8192}
        if mode not in mode_to_size:
            return '오퍼레이터님! 잘못된 모드입니다. 2k, 4k, 8k 중 하나를 선택해주세요.'
    
        size = mode_to_size[mode]
        if self.runner and hasattr(self.runner, 'restart_server'):
            self.runner.restart_server(context_size=size)
    
        self.context_size = size
        self.memory.set_mode(mode)
    
        confirmation_messages = {
            '2k': '2k VRAM 저장 모드가 활성화되었습니다.',
            '4k': '4k 균형 잡힌 표준 모드가 활성화되었습니다.',
            '8k': '8k 깊은 메모리 확장 모드가 활성화되었습니다.'
        }
    
        return confirmation_messages[mode]

    def classify_intent(self, user_query: str, rag_top_score: float = 0.0) -> str:
        q_lower = user_query.strip().lower()
        if any(k in q_lower for k in SMALLTALK_ABOUT_ORDIS):
            return 'SMALLTALK'

        is_question = any(q in q_lower for q in QUESTION_WORDS)
        if any(m in q_lower for m in TODO_MARKERS) and not is_question:
            return 'TODO'

        has_guide_kw = any(kw in q_lower for kw in GUIDE_KEYWORDS)
        # Search only returns chunks that cover the question, so any score means the docs answer it.
        has_answer = rag_top_score > 0
        names_drop_item = bool(DROP_QUESTION.search(q_lower) and self.drop_index.resolve_item(q_lower)[0])

        # '하이' must stand alone: it also starts names like 하이드로이드.
        is_greeting = re.search(r'(^|\s)하이($|[\s!~.,])', q_lower) is not None
        if not (has_guide_kw or names_drop_item) and (is_greeting or any(k in q_lower for k in SMALLTALK_CASUAL)):
            return 'SMALLTALK'

        # A game question goes to the guide path even without docs, which then says the data is missing.
        if has_guide_kw or names_drop_item or (has_answer and is_question):
            return 'GUIDE'
        # Nothing left to go on: casual remarks stay casual without spending a model call.
        if not has_answer and not is_question:
            return 'SMALLTALK'

        # [Step 1] 1-Token 도메인 분류 (초단문 프롬프트 + GBNF 문법 제약으로 1단어 생성 후 즉시 종료)
        try:
            payload = {
                "messages": [
                    {"role": "system", "content": INTENT_PROMPT},
                    {"role": "user", "content": f'"{user_query}" ->'},
                ],
                "grammar": INTENT_GRAMMAR,
                "temperature": 0.0,
                "max_tokens": 4,
                "stream": False,
            }
            res = requests.post(self.llama_server_url, json=payload, timeout=5)
            if res.status_code == 200:
                data = res.json()
                choices = data.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "").strip().upper()
                    if content in INTENT_LABELS:
                        return content
        except Exception:
            pass

        return 'GUIDE' if has_answer else 'SMALLTALK'

    @staticmethod
    def select_domain_tools(domain: str) -> Dict[str, Dict[str, Any]]:
        """[Step 2-1] 도메인 분류 결과에 해당하는 도구만 압축 선별하여 반환합니다."""
        return dict(DOMAIN_TOOLS.get(domain.upper(), {}))

    def resolve_domain_tool(self, domain: str, user_query: str) -> Optional[Dict[str, Any]]:
        """[Step 2-2] 선별된 도메인 도구들과 동적 GBNF 문법만을 사용하여 정형 JSON 도구 호출을 추출합니다."""
        tools = self.select_domain_tools(domain)
        if not tools:
            return None

        grammar = build_gbnf_tool_grammar(tools)
        tool_lines = "\n".join(f"- {name}({', '.join(meta.get('args', []))}): {meta.get('desc', '')}" for name, meta in tools.items())
        enriched_query = user_query
        if any(p in user_query for p in TOOL_PRONOUNS):
            recent_kws = self.memory.get_recent_keywords()
            if recent_kws:
                enriched_query = f"[최근 키워드: {', '.join(recent_kws[:2])}] {user_query}"
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "사용자의 요청을 처리할 도구를 고르고 인자를 JSON으로 답하라. "
                        "인자에는 대상 이름만 짧게 쓰고 조사나 시간 표현은 빼라.\n"
                        f"사용 가능 도구:\n{tool_lines}"
                    ),
                },
                {"role": "user", "content": enriched_query},
            ],
            "grammar": grammar,
            "temperature": 0.0,
            "max_tokens": 64,
            "stream": False,
        }
        try:
            res = requests.post(self.llama_server_url, json=payload, timeout=5)
            if res.status_code == 200:
                choices = res.json().get("choices", [])
                if choices:
                    raw = choices[0].get("message", {}).get("content", "").strip()
                    parsed = json.loads(raw)
                    tool = parsed.get("tool") if isinstance(parsed, dict) else None
                    args = parsed.get("args") if tool in tools else None
                    if isinstance(args, dict) and set(args) == set(tools[tool].get("args", [])):
                        return parsed
        except Exception:
            pass
        return None


