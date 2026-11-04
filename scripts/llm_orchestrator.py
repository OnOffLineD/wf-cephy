import time
import json
import re
import requests
from typing import Dict, Any, Optional
import os
import random

from scripts.chroma_rag_retriever import ChromaRAGRetriever
from scripts.path_config import get_path
from scripts.short_term_memory import ShortTermMemory
from scripts.persona_manager import PersonaManager
from scripts.emotion_parser import EmotionParser

MOOD_INSTRUCTION = "답변 맨 첫머리에 반드시 현재 감정을 [MOOD:tactical|proud|worried|happy|glitch] 중 하나의 태그로 쓰세요."
# Always about Ordis or the app itself.
SMALLTALK_ABOUT_ORDIS = (
    '작동중', '작동 중', '살아있', '켜져', '상태 어때', '오디스 상태', '너 살아', '너 작동', '시스템 상태', '함선 상태', '특이사항', '함선',
    '자장가', '옥타비아', '인덱싱', '대화', '말투', '구분', '똑같', '변주', '인식률', '자연스럽', '챗봇'
)
# Casual only when the message has no game topic: "누구 잡아야 샤드 나와?" is a question.
SMALLTALK_CASUAL = ('안녕', '반가', '피곤', '배고', '밥', '식사', '고마', '감사', '수고', '심심', '졸려', '누구', '빵')

class LLMOrchestrator:
    def __init__(self,
                 model_path: str = "models/google_gemma-4-E2B-it-Q4_K_M.gguf", 
                 llama_server_url: str = "http://127.0.0.1:18080/v1/chat/completions",
                 diagnoser: Optional[Any] = None):
        self.model_path = get_path(model_path) if not os.path.isabs(model_path) else model_path
        self.llama_server_url = llama_server_url
        self._rag_retriever = None
        self.diagnoser = diagnoser
        self.runner = None
        self.context_size = 4096
        self.memory = ShortTermMemory(mode='4k')
        self.persona_manager = PersonaManager()
        self.emotion_parser = EmotionParser()

    @property
    def rag_retriever(self):
        if self._rag_retriever is None:
            self._rag_retriever = ChromaRAGRetriever()
        return self._rag_retriever

    @rag_retriever.setter
    def rag_retriever(self, val):
        self._rag_retriever = val

    def _persona_prompt(self) -> str:
        active = self.persona_manager.get_active_persona()
        return active.get("prompt", "") if isinstance(active, dict) else (active or "")

    def _call_llm(self, system_prompt: str, user_prompt: str, temperature: float = 0.5) -> Optional[str]:
        # Convert system_prompt to string if it's a dict
        if isinstance(system_prompt, dict):
            system_prompt = system_prompt.get("prompt") or str(system_prompt)

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

    def chat_guide(self, user_query: str) -> str:
            # Check for reload commands
            if any(keyword in user_query for keyword in ['/리로드', '공략 리로드', '공략 새로고침']):
                self.rag_retriever.build_index(force_rebuild=True)
                return '오퍼레이터님! rules/wiki_docs 공략 데이터베이스를 최신 상태로 리로드 완료했습니다!'

            # Retrieve chunks from RAG retriever
            chunks = self.rag_retriever.retrieve(user_query, top_k=2)
            if not chunks:
                return self.chat_smalltalk(user_query)

            # Filter out weak second chunk if top chunk is decisively stronger
            if len(chunks) > 1 and chunks[0].get('score', 0) >= chunks[1].get('score', 0) * 2:
                top_chunks = [chunks[0]]
            else:
                top_chunks = chunks[:2]

            # Format context_text
            context_text = "\n\n".join([f"[{c.get('title', '')} - {c.get('section', '')}]\n{c.get('content') or c.get('text') or ''}" for c in top_chunks])

            # Get conversation context from memory
            conversation_context = self.memory.get_context_for_prompt()
            conversation_context_text = f"[최근 대화 기록]\n{conversation_context}\n\n" if conversation_context else ""

            # Get active persona prompt
            persona_prompt = self._persona_prompt() or "충성스러운 집사"

            # Construct system_prompt based on active persona
            system_prompt = (
                f"당신은 세팔론 오디스입니다. 성격 및 어조 지침: {persona_prompt}\n"
                f"{MOOD_INSTRUCTION} 오퍼레이터의 질문에 대해 [참고 데이터]에서 추출된 사실을 2~4줄의 간결한 한국어로 요약하세요. "
                "동일한 문장이나 불릿을 절대로 반복하지 마십시오. 8-mod 빌드는 요청받지 않는 한 생성하지 마십시오."
            )

            # Build user_prompt
            user_prompt = f"오퍼레이터 질문: {user_query}\n\n{conversation_context_text}[참고 데이터]:\n{context_text}\n\n세팔론 오디스의 친절하고 정확한 답변:"

            # Call LLM
            response = self._call_llm(system_prompt, user_prompt, temperature=0.55)
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
                return "\n".join(cleaned_lines).strip()

            # Fallback when LLM call fails
            if top_chunks[0].get('score', 0) >= 3.0:
                ordis_headers = [
                    '📖 [세팔론 오디스 가이드]',
                    '🔧 [세팔론 오디스 조언]',
                    '🛡️ [세팔론 오디스 보안]',
                    '🚀 [세팔론 오디스 전략]'
                ]
                summary_header = random.choice(ordis_headers)
                summary_content = "\n\n".join([f"- {c.get('content') or c.get('text') or ''}" for c in top_chunks])
                return f"{summary_header}\n\n{summary_content}"
            else:
                return self.chat_smalltalk(user_query)

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

            # 5. Analyze query text
            q_lower = user_query.strip().lower()

            # Retrieve chunks (with pronoun context enrichment)
            search_query = user_query
            pronouns = ['거기서', '그거', '그 무기', '거긴', '그 미션', '그 보스', '거기는']
            if any(p in user_query for p in pronouns):
                recent_kws = self.memory.get_recent_keywords()
                if recent_kws:
                    search_query = f"{user_query} {' '.join(recent_kws[:2])}"

            retrieved = self.rag_retriever.retrieve(search_query, top_k=2)
            top_score = retrieved[0].get('score', 0.0) if retrieved else 0.0

            # Classify intent
            intent = self.classify_intent(user_query, top_score)

            # Decision logic: Guide vs Smalltalk
            if intent == 'GUIDE' and retrieved:
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

        todo_markers = [
            '돌아야', '해야', '가야', '잡아야', '깨야', '파밍해야', '사야', '돌거야', '갈거야', '할거야', '돌자', '가자', '잡을래', '잡으러', '가볼까', '시작할게', '출발', '달릴거', '숙제', '클리어', '완료', '다 했', '다했', '끝냈'
        ]
        question_markers = ['?', '뭐야', '뭔가', '무슨', '어디', '어떻게', '알려줘', '추천', '설명', '방법']
        if any(m in q_lower for m in todo_markers) and not any(q in q_lower for q in question_markers):
            return 'TODO'
    
        guide_keywords = [
            '무기', '추천', '티어', '출격', '스펙', '성유물', '드랍', '패턴', '약점', '스토리', '퀘스트', '선행', '공략', '기믹', '보스', '파밍', '오버가드', '엑시무스', '아콜', '프로핏', '테랄', '3랄', '익스플로이터', '로팔', '집정관', '아콘', '뉴워', '두번째꿈', '갈챔', '곱연산', '속성', '두비리', '강길', '모딩', '세팅', '레이텀', '토리드', '펠락스', '펜모어', '인카논', '부식', '바이러스', '생존', '이동방어', '방어', '섬멸', '포획', '도청', '첩보', '구출', '감청', '교란', '네트라셀', '아르키메디아', '미션', '샤드', '공략'
        ]
        has_guide_kw = any(kw in q_lower for kw in guide_keywords)

        # '하이' must stand alone: it also starts names like 하이드로이드.
        is_greeting = re.search(r'(^|\s)하이($|[\s!~.,])', q_lower) is not None
        if not has_guide_kw and (is_greeting or any(k in q_lower for k in SMALLTALK_CASUAL)):
            return 'SMALLTALK'

        if rag_top_score < 2.0 and not has_guide_kw:
            return 'SMALLTALK'
    
        try:
            payload = {
                "messages": [
                    {"role": "system", "content": "사용자의 입력이 워프레임 게임 공략/기믹/모딩/파밍 정보를 묻는 질문이면 GUIDE, 오늘 할 일/숙제/미션 수행 계획이나 완료 보고이면 TODO, 일상 대화/인사/농담/봇에 대한 피드백이면 SMALLTALK라고만 한 단어로 답하세요."},
                    {"role": "user", "content": user_query}
                ],
                "temperature": 0.0,
                "max_tokens": 10,
                "stream": False
            }
            res = requests.post(self.llama_server_url, json=payload, timeout=5)
            if res.status_code == 200:
                data = res.json()
                choices = data.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "").strip()
                    content_upper = content.upper()
                    if 'TODO' in content_upper:
                        return 'TODO'
                    elif 'SMALLTALK' in content_upper:
                        return 'SMALLTALK'
                    elif 'GUIDE' in content_upper and rag_top_score >= 2.0:
                        return 'GUIDE'
        except Exception:
            pass
    
        return 'GUIDE' if (has_guide_kw and rag_top_score >= 2.0) or rag_top_score >= 4.0 else 'SMALLTALK'

