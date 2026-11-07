from unittest.mock import MagicMock, patch

import pytest
import requests

from scripts.llm_orchestrator import CHAT_MOOD_GRAMMAR, INTENT_GRAMMAR, LLMOrchestrator, build_gbnf_tool_grammar
from scripts.world_state_tracker import WorldStateTracker


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


def test_step1_gbnf_one_token_intent_classification(orc):
    """[Step 1] 키워드로 확정되지 않는 모호한 질문은 GBNF 문법 제약(1-Token) 페이로드로 분류된다."""
    mock_res = MagicMock()
    mock_res.status_code = 200
    mock_res.json.return_value = {"choices": [{"message": {"content": "TODO"}}]}

    with patch("scripts.llm_orchestrator.requests.post", return_value=mock_res) as mock_post:
        result = orc.classify_intent("이따가 저녁 먹고 나서 뭐 좀 챙겨볼까?", rag_top_score=0.0)
        assert result == "TODO"
        assert mock_post.called
        sent_payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert sent_payload["grammar"] == INTENT_GRAMMAR
        assert sent_payload["max_tokens"] == 4
        assert sent_payload["temperature"] == 0.0
        system = sent_payload["messages"][0]["content"]
        # Each label is defined and shown with examples, not just listed.
        assert all(f"{label}:" in system and f"-> {label}" in system for label in ("GUIDE", "SMALLTALK", "TODO"))


@pytest.mark.parametrize("content, expected", [("SMALLTALK", "SMALLTALK"), ("guide", "GUIDE"), ("TODO 입니다", "SMALLTALK")])
def test_step1_only_accepts_an_exact_label(orc, content, expected):
    mock_res = MagicMock(status_code=200)
    mock_res.json.return_value = {"choices": [{"message": {"content": content}}]}
    with patch("scripts.llm_orchestrator.requests.post", return_value=mock_res):
        # No docs matched, so anything that isn't a clean label falls back to smalltalk.
        assert orc.classify_intent("이따가 저녁 먹고 나서 뭐 좀 챙겨볼까?", rag_top_score=0.0) == expected


def test_step2_dynamic_tool_filtering_and_gbnf_assembly(orc, tmp_path):
    """[Step 2] 도메인 분류 결과에 따라 해당 도메인 도구만 필터링하고 GBNF 문법을 동적으로 조립해 실행한다."""
    # 1. TODO 도메인 도구 필터링 확인 (GUIDE 도구는 완전히 제외됨)
    todo_tools = orc.select_domain_tools("TODO")
    assert set(todo_tools.keys()) == {"add_todo", "complete_todo", "delete_todo"}
    assert "search_wiki" not in todo_tools
    assert orc.select_domain_tools("SMALLTALK") == {}

    # 2. GBNF 문법 동적 조립 검증
    grammar = build_gbnf_tool_grammar(todo_tools)
    assert 'root ::= "{" ws "\\"tool\\":" ws ( call-add-todo | call-complete-todo | call-delete-todo ) ws "}"' in grammar
    assert 'call-add-todo ::= "\\"add_todo\\"" "," ws "\\"args\\":" ws "{" ws "\\"task\\":" ws string ws "}"' in grammar
    assert '"\\"complete_todo\\""' in grammar
    assert '"\\"delete_todo\\""' in grammar

    # 3. LLM GBNF 응답 파싱 및 WorldStateTracker 연동 실행 검증
    mock_res = MagicMock()
    mock_res.status_code = 200
    mock_res.json.return_value = {
        "choices": [{"message": {"content": '{"tool": "complete_todo", "args": {"task": "출격"}}'}}]
    }
    with patch("scripts.llm_orchestrator.requests.post", return_value=mock_res) as mock_post:
        tool_call = orc.resolve_domain_tool("TODO", "오늘 출격은 방금 다 끝냈어")
        assert tool_call == {"tool": "complete_todo", "args": {"task": "출격"}}
        sent_payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert sent_payload["grammar"] == grammar
        assert "search_wiki" not in sent_payload["messages"][0]["content"]

    tracker = WorldStateTracker(data_file=str(tmp_path / "checklist.json"))
    tracker.load_checklist()
    exec_res = tracker.execute_todo_tool(tool_call)
    assert exec_res is not None
    assert exec_res["action"] == "COMPLETE"
    assert [i["id"] for i in tracker.load_checklist() if i["done"]] == ["daily_sortie"]


def test_guide_grammar_gives_each_tool_only_its_own_argument():
    grammar = build_gbnf_tool_grammar(LLMOrchestrator.select_domain_tools("GUIDE"))
    rules = dict(line.split(" ::= ", 1) for line in grammar.splitlines())
    assert '"\\"query\\":"' in rules["call-search-wiki"] and '"\\"item\\":"' not in rules["call-search-wiki"]
    assert '"\\"item\\":"' in rules["call-lookup-drop"] and '"\\"query\\":"' not in rules["call-lookup-drop"]


def test_step2_rejects_a_call_with_another_tools_arguments():
    orc = LLMOrchestrator()
    mock_res = MagicMock(status_code=200)
    mock_res.json.return_value = {"choices": [{"message": {"content": '{"tool": "search_wiki", "args": {"item": "넥스"}}'}}]}
    with patch("scripts.llm_orchestrator.requests.post", return_value=mock_res):
        assert orc.resolve_domain_tool("GUIDE", "넥스 어디서 나와") is None


def _todo_orc(tmp_path, tool_json):
    orc = LLMOrchestrator()
    orc.todo_tracker = WorldStateTracker(data_file=str(tmp_path / "checklist.json"))
    orc.todo_tracker.load_checklist()
    orc.classify_intent = lambda *_: "TODO"
    orc.chat_smalltalk = MagicMock(return_value="[MOOD:happy:1] 잡담")
    mock_res = MagicMock(status_code=200)
    mock_res.json.return_value = {"choices": [{"message": {"content": tool_json}}]}
    return orc, mock_res


def test_chat_ticks_an_existing_item_for_a_todo_message(tmp_path):
    orc, mock_res = _todo_orc(tmp_path, '{"tool": "complete_todo", "args": {"task": "출격"}}')
    with patch("scripts.llm_orchestrator.requests.post", return_value=mock_res):
        res = orc.chat("아까 출격 끝내고 왔지")
    assert res["type"] == "TODO_DONE"
    assert [i["id"] for i in orc.todo_tracker.load_checklist() if i["done"]] == ["daily_sortie"]
    orc.chat_smalltalk.assert_not_called()


@pytest.mark.parametrize("tool_json, tool", [
    ('{"tool": "add_todo", "args": {"task": "나이트웨이브"}}', "add_todo"),
    ('{"tool": "delete_todo", "args": {"task": "출격"}}', "delete_todo"),
])
def test_chat_asks_before_adding_or_deleting(tmp_path, tool_json, tool):
    orc, mock_res = _todo_orc(tmp_path, tool_json)
    before = orc.todo_tracker.load_checklist()
    with patch("scripts.llm_orchestrator.requests.post", return_value=mock_res):
        res = orc.chat("이따 그거 정리해야겠다")
    assert res["type"] == "TODO_CONFIRM" and res["tool"] == tool
    assert orc.todo_tracker.load_checklist() == before


def test_chat_falls_back_to_smalltalk_when_the_todo_names_nothing(tmp_path):
    orc, mock_res = _todo_orc(tmp_path, '{"tool": "complete_todo", "args": {"task": "보라색"}}')
    with patch("scripts.llm_orchestrator.requests.post", return_value=mock_res):
        res = orc.chat("보라색 다 했다")
    assert res["type"] == "SMALLTALK"
    assert not any(i["done"] for i in orc.todo_tracker.load_checklist())


def test_short_term_memory_pronoun_bridge_with_gbnf_step2():
    """단기 기억(ShortTermMemory)에 저장된 직전 주제가 대명사('그거') 발화 시 5토큰 키워드 힌트로 Step 2에 전달된다."""
    orc = LLMOrchestrator()
    orc.memory.add_turn("오늘 집정관 사냥 보상 뭐야?", "집정관 샤드를 얻을 수 있습니다.")

    mock_res = MagicMock()
    mock_res.status_code = 200
    mock_res.json.return_value = {
        "choices": [{"message": {"content": '{"tool": "complete_todo", "args": {"task": "집정관"}}'}}]
    }
    with patch("scripts.llm_orchestrator.requests.post", return_value=mock_res) as mock_post:
        tool_call = orc.resolve_domain_tool("TODO", "그거 방금 클리어했어")
        assert tool_call == {"tool": "complete_todo", "args": {"task": "집정관"}}
        user_msg = (mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json"))["messages"][1]["content"]
        assert "집정관" in user_msg
        assert "샤드를 얻을 수 있습니다" not in user_msg


def test_chat_mood_and_intensity_prefix_gbnf():
    """잡담/대화 생성 시 [MOOD:감정:강도(1~3)] 프리픽스를 강제하는 CHAT_MOOD_GRAMMAR가 적용되어 감정·강도·대화가 정확히 분리된다."""
    orc = LLMOrchestrator()
    mock_res = MagicMock()
    mock_res.status_code = 200
    mock_res.json.return_value = {
        "choices": [{"message": {"content": "[MOOD:glitch:3] 오퍼레이터님! 오늘도 전장을 --피로 물들이고-- 평화롭게 수호하십시오!"}}]
    }
    with patch("scripts.llm_orchestrator.requests.post", return_value=mock_res) as mock_post:
        res = orc.chat("안녕 오디스")
        assert mock_post.called
        sent_payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert sent_payload["grammar"] == CHAT_MOOD_GRAMMAR
        assert res["mood"] == "glitch"
        assert res["intensity"] == 3
        assert res["report"] == "오퍼레이터님! 오늘도 전장을 --피로 물들이고-- 평화롭게 수호하십시오!"


@pytest.mark.parametrize("query", ["오늘 할 일로 추가해줘", "숙제에 등록해줘"])
def test_todo_add_orders_are_classified_as_todo(orc, query):
    assert orc.classify_intent(query) == "TODO"


def test_chat_todo_explicit_add_uses_last_topic_and_adds_at_once(tmp_path):
    orc = LLMOrchestrator()
    orc.todo_tracker = WorldStateTracker(data_file=str(tmp_path / "checklist.json"))
    orc.todo_tracker.load_checklist()
    orc.chat_smalltalk = MagicMock(return_value="[MOOD:happy:1] 잡담")
    orc.memory.add_turn("신스 디컨스트럭트 어디서 나와?", "신스 디컨스트럭트는 ...")
    res = orc.chat("오늘 할 일로 추가해줘")
    assert res["type"] == "TODO_DONE"
    assert "신스 디컨스트럭트" in [i["text"] for i in orc.todo_tracker.load_checklist()]
    orc.chat_smalltalk.assert_not_called()


def test_chat_todo_explicit_add_from_model_tool_is_done_at_once(tmp_path):
    orc, mock_res = _todo_orc(tmp_path, '{"tool": "add_todo", "args": {"task": "나이트웨이브"}}')
    with patch("scripts.llm_orchestrator.requests.post", return_value=mock_res):
        res = orc.chat("나이트웨이브 넣어줘")
    assert res["type"] == "TODO_DONE"
    assert "나이트웨이브" in [i["text"] for i in orc.todo_tracker.load_checklist()]



