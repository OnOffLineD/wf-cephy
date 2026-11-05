import pytest
from PIL import Image
from scripts.screen_mod_analyzer import ScreenModAnalyzer
from scripts.llm_orchestrator import LLMOrchestrator

def test_interactive_weapon_clarification():
    analyzer = ScreenModAnalyzer()
    
    # 1. Image where weapon title cannot be detected
    dummy_img = Image.new("RGB", (400, 200), color=(0, 0, 0))
    res1 = analyzer.diagnose_screenshot(dummy_img)
    
    assert res1['success'] is False
    assert res1.get('needs_clarification') is True
    assert analyzer.has_pending_diagnosis() is True
    assert "어떤 무기인지" in res1['message'] or "무기의 이름이 무엇인지" in res1['message']
    
    # 2. User clarifies weapon name conversationally
    res2 = analyzer.resume_pending_diagnosis("쿠바 구울소우야")
    assert res2['success'] is True
    assert res2['weapon'] == 'Kuva Ghoulsaw'
    assert analyzer.has_pending_diagnosis() is False
    assert "Kuva Ghoulsaw" in res2['message']

def test_orchestrator_interactive_chat_routing():
    orchestrator = LLMOrchestrator()
    analyzer = ScreenModAnalyzer()
    orchestrator.diagnoser = analyzer
    
    # Simulate pending screenshot
    dummy_img = Image.new("RGB", (400, 200), color=(0, 0, 0))
    analyzer.diagnose_screenshot(dummy_img)
    assert analyzer.has_pending_diagnosis() is True
    
    # 1. User replies with weapon in chat
    chat_res = orchestrator.chat("이거 토리드인데")
    assert chat_res['type'] == 'DIAGNOSIS_CLARIFIED'
    assert 'Torid' in chat_res['report']
    assert analyzer.has_pending_diagnosis() is False
    
    # 2. Test cancellation
    analyzer.diagnose_screenshot(dummy_img)
    assert analyzer.has_pending_diagnosis() is True
    cancel_res = orchestrator.chat("아냐 취소할래")
    assert cancel_res['type'] == 'SMALLTALK'
    assert "취소" in cancel_res['report']
    assert analyzer.has_pending_diagnosis() is False

    def test_supporter_bot_upgrades():
        # Test GuideRetriever hot-reloading and retrieval
        retriever = GuideRetriever()
        # Simulate file modification
        with open(os.path.join(retriever.wiki_dir, 'test_file.md'), 'w', encoding='utf-8') as f:
            f.write("# Test Header\nSome content here.")
        retriever.build_index(force_rebuild=True)
        result = retriever.retrieve("Test Header")
        assert "Some content here." in result[0].text
    
        # Test WorldStateTracker process_chat_todo_command
        tracker = WorldStateTracker()
        # Register a todo
        response = tracker.process_chat_todo_command('테스트임무 숙제 등록')
        assert '테스트임무' in response
        assert '등록되었습니다' in response
        # Complete the todo
        response = tracker.process_chat_todo_command('테스트임무 완료')
        assert '테스트임무' in response
        assert '완료되었습니다' in response
        # Delete the todo
        response = tracker.process_chat_todo_command('테스트임무 숙제 삭제')
        assert '테스트임무' in response
        assert '삭제되었습니다' in response
    
        # Test ScreenModAnalyzer parse_stats
        analyzer = ScreenModAnalyzer()
        stats_text = "1O0.5 crit_chance, 25.O% crit_damage"
        parsed_stats = analyzer.parse_stats(stats_text)
        assert parsed_stats['crit_chance'] == 100.5
        assert parsed_stats['crit_damage'] == 25.0

