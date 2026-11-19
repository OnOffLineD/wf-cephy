import pytest
from scripts.llm_orchestrator import LLMOrchestrator

@pytest.fixture(scope="module")
def orchestrator():
    return LLMOrchestrator()

def test_chat_plan_intent_sortie(orchestrator):
    """'오늘 출격 돌거야' 같은 계획 발화는 RAG 가이드가 아닌 스몰톡 응원으로 분기되어야 함"""
    res = orchestrator.chat("오늘 출격 돌거야")
    assert res["type"] == "SMALLTALK"
    assert "출격" in res["report"] or "오디스" in res["report"]
    # 세드나 교차점 3번 복붙 버그가 없어야 함
    assert "세드나 교차점" not in res["report"]

def test_chat_survival_mission_guide(orchestrator):
    """'생존 미션은 뭐야?'는 실드게이팅이 아닌 산소/생명유지장치 가이드가 나와야 함"""
    res = orchestrator.chat("생존 미션은 뭐야?")
    assert res["type"] == "GUIDE"
    report = res["report"]
    assert any(w in report for w in ["산소", "생명 유지", "버티", "로테이션"])
    assert "실드 게이팅" not in report

def test_chat_mobile_defense_guide(orchestrator):
    """'이동방어는 무슨 미션이야?'는 침대/숙면 환각 없이 데이터매스/터미널 설명이 나와야 함"""
    res = orchestrator.chat("이동방어는 무슨 미션이야?")
    assert res["type"] == "GUIDE"
    report = res["report"]
    assert any(w in report for w in ["데이터매스", "터미널", "방어", "해킹"])
    assert "침대" not in report
    assert "숙면" not in report

def test_chat_status_check(orchestrator):
    """'오디스 상태 어때?'는 상태이상 설명이 아닌 오디스 무결성 100% 정상 작동이 나와야 함"""
    res = orchestrator.chat("오디스 상태 어때?")
    assert res["type"] == "SMALLTALK"
    assert "정상 가동" in res["report"] or "함선 무결성" in res["report"]

def test_chat_disruption_guide(orchestrator):
    """'교란 미션 공략 알려줘'는 데몰리셔와 도관 열쇠 메커니즘을 설명해야 함"""
    res = orchestrator.chat("교란 미션 공략 알려줘")
    assert res["type"] == "GUIDE"
    report = res["report"]
    assert any(w in report for w in ["데몰리셔", "도관", "키", "열쇠", "성유물"])


# --- Routing regressions: app-meta words, saved-build lookups, TODO markers, a waiting screenshot ---

import time
from unittest.mock import MagicMock, patch

import requests

from scripts.build_store import BuildStore
from scripts.llm_orchestrator import LLM_LOADING_MESSAGE


@pytest.fixture
def offline():
    with patch("scripts.llm_orchestrator.requests.post", side_effect=requests.ConnectionError()) as post:
        yield post


def _intent(orc, query):
    retrieved = orc.rag_retriever.retrieve(query, top_k=2)
    return orc.classify_intent(query, retrieved[0]["score"] if retrieved else 0.0)


@pytest.mark.parametrize("query", ["코퍼스 함선 미션 어떻게 깨?", "그리니어 함선 보스 약점 알려줘", "옥타비아 세팅 추천해줘"])
def test_game_questions_with_app_meta_words_are_guide(orchestrator, offline, query):
    assert _intent(orchestrator, query) == "GUIDE"


@pytest.mark.parametrize("query", ["함선 특이사항 있어?", "너 대화가 자꾸 똑같네", "옥타비아 자장가 틀어줘"])
def test_app_meta_words_alone_stay_smalltalk(orchestrator, offline, query):
    assert _intent(orchestrator, query) == "SMALLTALK"


def test_ship_mention_is_not_a_status_check():
    orc = LLMOrchestrator()
    orc._call_llm = MagicMock(return_value="[MOOD:happy:1] 꾸미기 좋지요")
    assert "함선 무결성" not in orc.chat_smalltalk("함선 꾸미기 하고 싶어")
    assert "함선 무결성" in orc.chat_smalltalk("함선 상태 어때?")


@pytest.mark.parametrize("query", ["레일잭 미션 클리어 보상 정리", "리벤 추가 옵션 종류", "엔도 파밍해야 하는 곳"])
def test_weak_todo_markers_next_to_a_game_topic_are_guide(orchestrator, offline, query):
    assert _intent(orchestrator, query) == "GUIDE"


@pytest.mark.parametrize("query", ["오늘 출격 돌거야", "아콘 샤드 숙제에 추가해줘", "레일잭 오늘 해야겠다", "보라색 다 했다"])
def test_plans_and_checklist_orders_stay_todo(orchestrator, offline, query):
    assert _intent(orchestrator, query) == "TODO"


def _build_orc(tmp_path):
    store = BuildStore(str(tmp_path / "builds.json"))
    store.save_build({"weapon": "Soma", "kr_name": "소마", "slots": {"R1_C1": "Serration"}})
    soma = {"name": "Soma", "kr_name": "소마"}
    diagnoser = MagicMock()
    diagnoser.build_store = store
    diagnoser.indexer.match_weapon_strict.side_effect = lambda text, min_ratio=92.0: soma if text == "소마" else None
    diagnoser.format_saved_build.return_value = "저장된 소마 빌드"
    orc = LLMOrchestrator()
    orc.diagnoser = diagnoser
    orc._call_llm = MagicMock(return_value=None)
    return orc


@pytest.mark.parametrize("query", ["소마 세팅 뭐가 좋아?", "소마 모드 뭐가 괜찮아?", "소마 빌드 뭐 써야 돼?"])
def test_build_advice_questions_are_not_saved_build_lookups(tmp_path, query):
    assert _build_orc(tmp_path)._answer_build_query(query) is None


@pytest.mark.parametrize("query", ["소마 모드 뭐 꼈어?", "소마 모드 알려줘"])
def test_questions_about_own_build_still_read_storage(tmp_path, query):
    res = _build_orc(tmp_path)._answer_build_query(query)
    assert res["type"] == "BUILD_QUERY" and "저장된 소마 빌드" in res["report"]


def _waiting_orc():
    orc = LLMOrchestrator()
    diagnoser = MagicMock()
    diagnoser.has_pending_bonus.return_value = False
    diagnoser.has_pending_riven.return_value = False
    diagnoser.has_pending_diagnosis.return_value = True
    diagnoser.resume_pending_diagnosis.return_value = {"success": False, "invalid_weapon": True, "message": "무기를 특정하지 못했습니다"}
    orc.diagnoser = diagnoser
    orc._call_llm = MagicMock(return_value="[MOOD:happy:1] 네, 오퍼레이터님")
    return orc, diagnoser


@pytest.mark.parametrize("query, expected", [
    ("코퍼스 함선 미션 어떻게 깨?", "GUIDE"),
    ("오늘 진짜 피곤하다", "SMALLTALK"),
    ("안녕 오디스", "SMALLTALK"),
    ("오늘 출격 돌거야", "SMALLTALK"),
])
def test_waiting_screenshot_does_not_swallow_other_messages(offline, query, expected):
    orc, diagnoser = _waiting_orc()
    res = orc.chat(query)
    assert res["type"] == expected
    diagnoser.resume_pending_diagnosis.assert_not_called()
    # The scan keeps waiting for its weapon name.
    diagnoser.clear_pending_diagnosis.assert_not_called()


def test_waiting_screenshot_still_takes_a_weapon_name(offline):
    orc, diagnoser = _waiting_orc()
    diagnoser.resume_pending_diagnosis.return_value = {"success": True, "message": "토리드 진단 완료"}
    res = orc.chat("이거 토리드인데")
    assert res["type"] == "DIAGNOSIS_CLARIFIED"
    diagnoser.resume_pending_diagnosis.assert_called_once_with("이거 토리드인데")


def test_unknown_short_name_asks_again_but_short_game_topic_is_answered(offline):
    orc, diagnoser = _waiting_orc()
    assert orc.chat("부메랑칼")["type"] == "CLARIFICATION_FAILED"
    assert orc.chat("아콘 샤드")["type"] == "GUIDE"


# --- LLM off / loading ---

def _orc_with_runner(starting: bool, healthy: bool):
    orc = LLMOrchestrator()
    orc.runner = MagicMock()
    orc.runner.is_starting.return_value = starting
    orc.runner.is_healthy.return_value = healthy
    return orc


def test_offline_llm_is_not_waited_for():
    orc = _orc_with_runner(starting=False, healthy=False)
    started = time.time()
    with patch("scripts.llm_orchestrator.requests.post") as post:
        assert orc._call_llm("system", "안녕") is None
    assert time.time() - started < 1
    orc.runner.wait_for_ready.assert_not_called()
    post.assert_not_called()


def test_loading_notice_is_shown_for_smalltalk_but_not_remembered():
    orc = _orc_with_runner(starting=True, healthy=False)
    res = orc.chat("오디스 오늘 기분 어때")
    assert res["report"] == LLM_LOADING_MESSAGE
    assert LLM_LOADING_MESSAGE not in orc.memory.get_context_for_prompt()


def test_loading_notice_never_ends_up_in_a_guide_answer():
    orc = _orc_with_runner(starting=True, healthy=False)
    res = orc.chat("교란 미션 공략 알려줘")
    assert res["type"] == "GUIDE"
    assert LLM_LOADING_MESSAGE not in res["report"]
    assert any(w in res["report"] for w in ["데몰리셔", "도관", "키", "열쇠", "성유물"])
