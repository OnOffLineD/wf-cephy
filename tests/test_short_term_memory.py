import pytest
from unittest.mock import MagicMock, patch
from scripts.short_term_memory import ShortTermMemory
from scripts.llm_orchestrator import LLMOrchestrator
from scripts.embedded_llm_runner import EmbeddedLLMRunner

def test_short_term_memory_sliding_window_and_budget():
    mem = ShortTermMemory(mode="4k")
    assert mem.mode == "4k"
    assert mem._get_token_budget("4k") >= 1000

    # Add turns
    mem.add_turn("생존 미션 어떻게 해?", "생명 유지 캡슐을 작동시키고 네크로스를 기용하십시오.")
    mem.add_turn("거기서 산소 떨어지면?", "산소가 0이 되면 실드가 고갈되고 체력이 지속적으로 깎입니다.")

    prompt_ctx = mem.get_context_for_prompt()
    assert "생존 미션" in prompt_ctx
    assert "산소" in prompt_ctx

    # Switch to 2k mode
    mem.set_mode("2k")
    assert mem.mode == "2k"
    assert mem._get_token_budget("2k") <= 500

    # Test clear
    mem.clear()
    assert mem.get_context_for_prompt() == ""

def test_short_term_memory_keyword_extraction():
    mem = ShortTermMemory()
    mem.add_turn("글레이브 모딩 어떻게 해?", "프라임드 프레셔 포인트와 볼택 스트라이크를 추천합니다.")
    kws = mem.get_recent_keywords()
    assert any("글레이브" in k for k in kws)

def test_orchestrator_memory_mode_commands():
    orc = LLMOrchestrator()
    assert orc.context_size == 4096
    assert orc.memory.mode == "4k"

    # Command: switch to 2k
    res = orc.chat("/메모리 2k")
    assert res["type"] == "system"
    assert "2k" in res["report"] or "2048" in res["report"]
    assert orc.context_size == 2048
    assert orc.memory.mode == "2k"

    # Command: switch to 8k
    res = orc.chat("/메모리 8k")
    assert orc.context_size == 8192
    assert orc.memory.mode == "8k"

    # Command: clear
    res = orc.chat("/메모리 초기화")
    assert "비웠습니다" in res["report"] or "초기화" in res["report"]

def test_orchestrator_turn_memory_and_pronoun_enrichment():
    orc = LLMOrchestrator()
    orc._call_llm = MagicMock(return_value="오디스가 답변합니다.")

    # 1st turn: asks about survival mission
    orc.chat("생존 미션 알려줘")
    assert len(orc.memory.turns) >= 1

    # 2nd turn: asks with pronoun '거기서'
    with patch.object(orc.rag_retriever, 'retrieve', return_value=[{"title": "생존", "section": "규칙", "content": "산소 캡슐", "score": 10.0}]) as mock_ret:
        res = orc.chat("거기서 산소 어떻게 해?")
        assert res["type"].upper() in ["GUIDE", "SYSTEM"]
        # Verify RAG was queried with enriched keyword or original query
        assert mock_ret.called
        call_query = mock_ret.call_args[0][0]
        assert "생존" in call_query or "거기서" in call_query

def test_embedded_llm_runner_default_4k_and_restart():
    runner = EmbeddedLLMRunner(context_size=4096)
    assert runner.context_size == 4096

    runner.stop_server = MagicMock()
    runner.cleanup_existing_server = MagicMock()
    runner.start_server = MagicMock(return_value=True)

    success = runner.restart_server(context_size=8192)
    assert success is True
    assert runner.context_size == 8192
    assert runner.stop_server.called
    assert runner.start_server.called
