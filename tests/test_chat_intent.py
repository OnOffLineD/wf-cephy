from unittest.mock import MagicMock, patch

import pytest
import requests

from scripts.llm_orchestrator import LLMOrchestrator


@pytest.fixture(scope="module")
def orc():
    return LLMOrchestrator()


@pytest.fixture(autouse=True)
def llm_offline():
    with patch("scripts.llm_orchestrator.requests.post", side_effect=requests.ConnectionError()):
        yield


def intent(orc, query):
    retrieved = orc.rag_retriever.retrieve(query, top_k=2)
    return orc.classify_intent(query, retrieved[0]["score"] if retrieved else 0.0)


@pytest.mark.parametrize("query", ["하이", "하이 오디스", "안녕 오디스", "피곤하다", "오늘 뭐하지", "베루스 어때", "오디스 상태 어때?"])
def test_casual_messages_are_smalltalk(orc, query):
    assert intent(orc, query) == "SMALLTALK"


@pytest.mark.parametrize("query", ["하이드로이드 공략 알려줘", "토리드 스펙 알려줘", "아이돌론 사냥 방법", "누구 잡아야 샤드 나와?", "오버가드 약점"])
def test_game_questions_are_guide(orc, query):
    assert intent(orc, query) == "GUIDE"


@pytest.mark.parametrize("query", ["오늘 뭐하지", "베루스 어때", "피곤하다"])
def test_common_words_do_not_match_weapons(orc, query):
    assert not [c for c in orc.rag_retriever.retrieve(query, top_k=3) if "스펙" in c.get("title", "")]


@pytest.mark.parametrize("query, name", [("토리드 스펙", "Torid"), ("쿠바 자르 스펙", "Kuva Zarr"), ("글레이브 프라임 스펙", "Glaive Prime")])
def test_weapon_names_get_a_fact_card(orc, query, name):
    assert name in orc.rag_retriever.retrieve(query, top_k=1)[0]["title"]


@pytest.mark.parametrize("query", ["아콘 샤드 파밍", "샤드 나와?"])
def test_player_slang_finds_archon_docs(orc, query):
    assert "집정관" in orc.rag_retriever.retrieve(query, top_k=1)[0]["title"]


def test_warframe_gets_its_own_card(orc):
    top = orc.rag_retriever.retrieve("하이드로이드 공략", top_k=1)[0]
    assert "Hydroid" in top["title"]
    assert "체력" in top["text"]
    assert "치명타" not in top["text"]


def test_guide_prompt_uses_persona_text_not_raw_dict():
    orc = LLMOrchestrator()
    orc.persona_manager.get_active_persona = lambda: {"id": "x", "name": "테스트", "desc": "설명", "prompt": "짧게 답하세요"}
    orc._call_llm = MagicMock(return_value="[MOOD:happy] 답변")
    orc.rag_retriever = MagicMock()
    orc.rag_retriever.retrieve.return_value = [{"title": "t", "section": "s", "text": "내용", "score": 10.0}]
    orc.chat_guide("공략")
    system_prompt = orc._call_llm.call_args[0][0]
    assert "짧게 답하세요" in system_prompt
    assert "{'id'" not in system_prompt


def test_smalltalk_prompt_has_memory_and_mood_instruction():
    orc = LLMOrchestrator()
    orc.persona_manager.get_active_persona = lambda: {"prompt": "다정하게"}
    orc.memory.add_turn("내 이름은 테노야", "반갑습니다")
    orc._call_llm = MagicMock(return_value="[MOOD:happy] 네")
    orc.chat_smalltalk("내 이름 기억해?")
    system_prompt, user_prompt = orc._call_llm.call_args[0][:2]
    assert "[MOOD:" in system_prompt and "다정하게" in system_prompt
    assert "테노" in user_prompt and "내 이름 기억해?" in user_prompt
