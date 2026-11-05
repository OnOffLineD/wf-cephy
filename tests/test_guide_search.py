import json
import os
from unittest.mock import MagicMock, patch

import pytest
import requests

from scripts.drop_lookup import DropIndex, _parse_item
from scripts.guide_retriever import GuideRetriever, _compact
from scripts.llm_orchestrator import NO_DATA_REPLY, LLMOrchestrator
from scripts.path_config import get_path, get_user_data_path
from scripts.short_term_memory import TOKENS_PER_CHAR, ShortTermMemory

QUESTIONS = json.load(open(get_path("tests/fixtures/guide_questions.json"), encoding="utf-8"))["questions"]
COVERED = [q for q in QUESTIONS if q["expect"]]
UNCOVERED = [q for q in QUESTIONS if not q["expect"]]


@pytest.fixture(scope="module")
def retriever():
    return GuideRetriever()


@pytest.fixture(scope="module")
def drops():
    return DropIndex()


@pytest.fixture
def orc():
    orchestrator = LLMOrchestrator()
    orchestrator._call_llm = MagicMock(return_value=None)
    with patch("scripts.llm_orchestrator.requests.post", side_effect=requests.ConnectionError()):
        yield orchestrator


def doc_titles(retriever, query):
    return [h["title"] for h in retriever.retrieve(query, top_k=4) if h["type"] == "wiki"]


def test_covered_questions_find_their_doc(retriever):
    misses = []
    for item in COVERED:
        titles = doc_titles(retriever, item["q"])
        if not (titles and any(e in titles[0] for e in item["expect"])):
            misses.append((item["q"], titles[:1]))
    # 47/48 at the time of writing, up from 40/48 with keyword scoring.
    assert len(misses) <= 1, misses


def test_uncovered_questions_mostly_find_nothing(retriever):
    false_hits = [(item["q"], doc_titles(retriever, item["q"])[:1]) for item in UNCOVERED if doc_titles(retriever, item["q"])]
    # 2/9 at the time of writing, down from 7/9 with keyword scoring.
    assert len(false_hits) <= 2, false_hits


@pytest.mark.parametrize("slang, official", [("렐릭", "성유물"), ("방깎", "삭감"), ("스틸패스", "강철"), ("인페", "인페스티드")])
def test_slang_is_mapped_to_doc_wording(retriever, slang, official):
    assert any(official in word for word in retriever._query_words(f"{slang} 알려줘")[1])


def test_spacing_does_not_matter(retriever):
    assert _compact("두번째 꿈") == _compact("두 번째 꿈")
    assert "The_Second_Dream" in doc_titles(retriever, "두번째꿈 보상")[0]


def test_question_wording_alone_finds_nothing(retriever):
    assert retriever.retrieve("어떻게 해", top_k=3) == []


def test_docs_reload_when_a_file_appears(tmp_path):
    (tmp_path / "a.md").write_text("# 첫 문서\n## 섹션\n테스트내용입니다", encoding="utf-8")
    retriever = GuideRetriever(wiki_dir=str(tmp_path))
    assert retriever.retrieve("테스트내용")
    (tmp_path / "b.md").write_text("# 둘째 문서\n## 섹션\n새로운자료입니다", encoding="utf-8")
    assert "둘째 문서" in retriever.retrieve("새로운자료")[0]["title"]


def test_long_sections_are_cut_at_line_ends(tmp_path):
    lines = "\n".join(f"{i}번째 줄의 내용입니다" for i in range(200))
    (tmp_path / "a.md").write_text(f"# 긴 문서\n## 섹션\n{lines}", encoding="utf-8")
    retriever = GuideRetriever(wiki_dir=str(tmp_path))
    pieces = [d["text"] for d in retriever.documents if d["source"] == "wiki"]
    assert len(pieces) > 1
    assert all(p.endswith("내용입니다") for p in pieces)


@pytest.mark.parametrize("raw, parsed", [
    ("100 Endo", ("endo", 100)),
    ("3X 1,500 Credits Cache", ("credits", 4500)),
    ("2X Forma Blueprint", ("forma blueprint", 2)),
    ("Serration", ("serration", 1)),
])
def test_item_counts_are_parsed(raw, parsed):
    assert _parse_item(raw) == parsed


@pytest.mark.parametrize("query, word", [("포르마 파밍 어디서 해", "포르마"), ("엔도 어디서 나와", "엔도"), ("쿠바 어디서 나와", "쿠바"), ("서레이션 어디서 나와", "서레이션")])
def test_drop_answers_name_the_item(drops, query, word):
    answer = drops.answer(query)
    assert word in answer and "확률" in answer


def test_best_place_questions_admit_the_table_limit(drops):
    assert "시간당 효율" in drops.answer("엔도 파밍 어디가 좋아")
    assert "시간당 효율" not in drops.answer("엔도 어디서 나와")


def test_questions_without_an_item_get_no_drop_answer(drops):
    assert drops.answer("오늘 어디 가지") is None
    assert drops.answer("포르마 뭐야") is None


def test_event_missions_and_vaulted_relics_are_not_offered(drops):
    answer = drops.answer("포르마 어디서 나와")
    relic_line = next(line for line in answer.splitlines() if line.startswith("[성유물]"))
    assert "획득 가능" in relic_line
    total, available = [int(n) for n in __import__("re").findall(r"(\d+)종", relic_line)]
    assert available < total


def test_relic_contents_keep_working_after_leaving_the_search(drops):
    answer = drops.answer_relic("액시 A1 보상 뭐야")
    assert "Axi A1" in answer and "Prime" in answer
    assert drops.answer_relic("집정관 보상 뭐야") is None


@pytest.mark.parametrize("query", [q["q"] for q in QUESTIONS])
def test_every_game_question_takes_the_guide_path(orc, query):
    retrieved = orc.rag_retriever.retrieve(query, top_k=2)
    assert orc.classify_intent(query, retrieved[0]["score"] if retrieved else 0.0) == "GUIDE"


@pytest.mark.parametrize("query", ["오늘 출격 돌거야", "아마르 잡으러 가자", "쿠바 파밍해야지"])
def test_plans_stay_todo(orc, query):
    retrieved = orc.rag_retriever.retrieve(query, top_k=2)
    assert orc.classify_intent(query, retrieved[0]["score"] if retrieved else 0.0) == "TODO"


def test_beginner_question_is_not_a_todo(orc):
    assert orc.classify_intent("초보인데 뭐부터 해야돼") == "GUIDE"


def test_missing_data_is_said_out_loud_and_logged(orc):
    res = orc.chat("낚시 어떻게 해?")
    assert res["type"] == "GUIDE"
    assert res["report"] == orc.emotion_parser.parse(NO_DATA_REPLY)["clean_text"]
    orc._call_llm.assert_not_called()
    with open(get_user_data_path("logs", "guide-misses.jsonl"), encoding="utf-8") as f:
        assert "낚시 어떻게 해?" in f.read()


def test_drop_question_is_answered_from_the_table(orc):
    res = orc.chat("포르마 파밍 어디서 해")
    assert res["type"] == "DROP_INFO"
    assert "확률" in res["report"]


def test_guide_titled_after_the_item_beats_the_table(orc):
    res = orc.chat("힐드린 어디서 얻어")
    assert res["type"] == "GUIDE"
    assert "익스플로이터" in res["report"]


def test_guide_answer_cites_its_source(orc):
    orc._call_llm.return_value = "[MOOD:tactical] 머리를 노리십시오."
    res = orc.chat("아마르 어떻게 잡아?")
    assert "머리를 노리십시오" in res["report"]
    assert "📎 근거: 집정관 아마르" in res["report"]


def test_answer_lines_with_invented_numbers_are_removed(orc):
    orc._call_llm.return_value = "[MOOD:tactical] 분신을 먼저 구분하십시오.\n피해가 987654% 늘어납니다."
    report = orc.chat("아마르 어떻게 잡아?")["report"]
    assert "분신을 먼저" in report
    assert "987654" not in report


def test_model_failure_falls_back_to_source_text(orc):
    report = orc.chat("아마르 어떻게 잡아?")["report"]
    assert "오버가드" in report or "약점" in report
    assert "📎 근거" in report


def test_prompt_asks_for_the_answer_first_and_no_invention(orc):
    orc._call_llm.return_value = "[MOOD:happy] 답"
    orc.chat_guide("아마르 어떻게 잡아?")
    system_prompt, user_prompt = orc._call_llm.call_args[0][:2]
    assert "첫 문장" in system_prompt and "지어내지" in system_prompt
    assert "먼저" in system_prompt
    assert "[참고 데이터]" in user_prompt and "집정관 아마르" in user_prompt
    assert orc._call_llm.call_args[1]["temperature"] <= 0.2


def test_drop_reply_does_not_ask_the_model_for_advice(orc):
    orc.chat("포르마 파밍 어디서 해")
    orc._call_llm.assert_not_called()


def test_context_stays_inside_the_budget(orc):
    chunks = [{"text": "가" * 1200, "score": 10.0}, {"text": "나" * 1200, "score": 9.0}, {"text": "다" * 1200, "score": 8.0}, {"text": "라", "score": 1.0}]
    kept = orc._guide_context_chunks(chunks)
    assert len(kept) == 2


def test_weakly_related_other_doc_stays_out_of_the_context(orc):
    chunks = [{"text": "가", "doc_title": "A", "score": 10.0}, {"text": "나", "doc_title": "A", "score": 6.0}, {"text": "다", "doc_title": "B", "score": 6.0}]
    assert [c["text"] for c in orc._guide_context_chunks(chunks)] == ["가", "나"]


def test_long_conversations_leave_room_for_the_guide_context():
    memory = ShortTermMemory(mode="4k")
    for i in range(30):
        memory.add_turn(f"{i}번째 질문입니다", "아주 긴 공략 답변입니다. " * 80 + "\n📎 근거: 문서")
    context = memory.get_context_for_prompt()
    assert len(context) * TOKENS_PER_CHAR <= memory.token_budget + 100
    assert "📎" not in context
    assert "29번째 질문" in context
