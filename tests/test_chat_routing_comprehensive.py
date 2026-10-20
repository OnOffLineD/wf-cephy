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
