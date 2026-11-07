import threading
from typing import List

# Measured on the bundled model: Korean prompts cost about 0.6 tokens per character.
TOKENS_PER_CHAR = 0.6
# Enough to follow up on a reply; long reports and tables would crowd out the guide context.
MAX_PROMPT_REPLY_CHARS = 240

class ShortTermMemory:
    def __init__(self, mode: str = '4k'):
        self.mode = mode
        self.token_budget = self._get_token_budget(mode)
        self.turns = []
        self.lock = threading.Lock()

    def set_mode(self, mode: str):
        if mode in ['2k', '4k', '8k']:
            self.mode = mode
            self.token_budget = self._get_token_budget(mode)
        else:
            raise ValueError("Mode must be one of '2k', '4k', '8k'.")

    def _get_token_budget(self, mode: str) -> int:
        budgets = {'2k': 350, '4k': 1200, '8k': 2500}
        return budgets.get(mode, 1200)  # Default to 4k if mode is invalid

    def add_turn(self, user_query: str, bot_response: str):
        with self.lock:
            turn = (user_query, bot_response, self._get_timestamp())
            self.turns.append(turn)
            self._prune_turns()

    def _get_timestamp(self) -> float:
        import time
        return time.time()

    def _prune_turns(self):
        while self.turns and self._estimate_total_tokens() > self.token_budget:
            self.turns.pop(0)

    @staticmethod
    def _prompt_reply(bot: str) -> str:
        reply = "\n".join(line for line in bot.splitlines() if not line.startswith("📎"))
        return reply[:MAX_PROMPT_REPLY_CHARS].strip()

    def _estimate_total_tokens(self) -> int:
        # Word counts badly undercount Korean, which let the prompt overflow the model's context.
        chars = sum(len(user) + len(self._prompt_reply(bot)) for user, bot, _ in self.turns)
        return int(chars * TOKENS_PER_CHAR)

    def get_context_for_prompt(self) -> str:
        with self.lock:
            context = ""
            for user, bot, _ in self.turns:
                context += f"User: {user}\nOrdis: {self._prompt_reply(bot)}\n"
            return context.strip()

    def get_recent_keywords(self) -> List[str]:
        import re
        stop_words = {'어떻게', '알려줘', '알려', '뭐야', '해', '이거', '그거', '저거', '어때', '좀', '추천', '세팅', '모딩', '알려주',
                      # Question and command words, so only the topic's nouns are left to carry over.
                      '어디서', '어디', '나와', '나와요', '나오', '나오나', '나옴', '드랍', '드롭', '얻어', '얻는', '파밍',
                      '추가', '추가해', '추가해줘', '등록', '등록해', '등록해줘', '숙제', '숙제로', '숙제에',
                      '할일', '할일로', '일로', '오늘', '내일'}
        keywords = []
        with self.lock:
            for user, _, _ in reversed(self.turns):
                tokens = re.findall(r'[\w가-힣]+', user)
                for t in tokens:
                    if len(t) >= 2 and t not in stop_words and t not in keywords:
                        keywords.append(t)
        return keywords[:5]

    def clear(self):
        with self.lock:
            self.turns.clear()

# Example usage:
if __name__ == "__main__":
    memory = ShortTermMemory()
    memory.add_turn("I need help with the Void Fiend mission.", "You should check the Warframe Codex.")
    memory.add_turn("What's the best Void Fiend weapon?", "The Voidfiend's Fury is highly recommended.")
    print(memory.get_context_for_prompt())
    print(memory.get_recent_keywords())
    memory.clear()