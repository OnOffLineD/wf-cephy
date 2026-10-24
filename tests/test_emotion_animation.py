import os
import pytest
from scripts.emotion_parser import EmotionParser
from scripts.llm_orchestrator import LLMOrchestrator

def test_emotion_parser_standard_tags():
    parser = EmotionParser()
    
    # 1. Standard tag
    res = parser.parse("[MOOD:happy] 오퍼레이터님! 오디스가 대기 중입니다!")
    assert res["clean_text"] == "오퍼레이터님! 오디스가 대기 중입니다!"
    assert res["mood"] == "happy"
    assert res["intensity"] == 2
    assert res["vfx"] is None

    # 2. Tag with intensity
    res2 = parser.parse("[MOOD:glitch:3] --적들의 뼈를 으스러뜨리십시오!-- ...오퍼레이터님?")
    assert res2["clean_text"] == "--적들의 뼈를 으스러뜨리십시오!-- ...오퍼레이터님?"
    assert res2["mood"] == "glitch"
    assert res2["intensity"] == 3

    # 3. Mixed emotions
    res3 = parser.parse("[MOOD:angry+sad] 억울하고 서럽습니다 오퍼레이터님...")
    assert res3["clean_text"] == "억울하고 서럽습니다 오퍼레이터님..."
    assert res3["mood"] == "angry"
    assert res3["secondary_mood"] == "sad"

    # 4. Tag with parameters (intensity & vfx)
    res4 = parser.parse("[MOOD:happy:3,vfx=blush] 정말 최고입니다!")
    assert res4["clean_text"] == "정말 최고입니다!"
    assert res4["mood"] == "happy"
    assert res4["intensity"] == 3
    assert res4["vfx"] == "blush"

    # 5. Korean alias
    res5 = parser.parse("[MOOD:걱정] 오퍼레이터님, 무리하지 마십시오!")
    assert res5["clean_text"] == "오퍼레이터님, 무리하지 마십시오!"
    assert res5["mood"] == "worried"

def test_emotion_parser_fallback_inference():
    parser = EmotionParser()

    # Glitch fallback
    res1 = parser.parse("적들을 찢어발기십시오!")
    assert res1["mood"] == "glitch"
    assert res1["clean_text"] == "적들을 찢어발기십시오!"

    # Worried fallback
    res2 = parser.parse("오퍼레이터님, 안전하게 조심해서 다녀오세요!")
    assert res2["mood"] == "worried"

    # Tactical fallback
    res3 = parser.parse("전장 데이터와 속성 약점을 정밀 분석 보고합니다.")
    assert res3["mood"] == "tactical"

    # Proud fallback
    res4 = parser.parse("오늘의 미션을 완벽하게 성공하셨습니다! 영광입니다!")
    assert res4["mood"] == "proud"

def test_orchestrator_chat_strips_tag_and_provides_mood():
    orch = LLMOrchestrator()
    res = orch.chat("안녕 오디스")
    assert "report" in res
    assert "[MOOD:" not in res["report"]
    assert "mood" in res
    assert "intensity" in res

def test_layered_pet_renderer_headless():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        from PySide6.QtWidgets import QApplication
    from scripts.layered_pet_renderer import LayeredPetRenderer

    app = QApplication.instance() or QApplication([])
    renderer = LayeredPetRenderer()
    
    # Test mood and intensity
    renderer.set_mood("happy", intensity=3, vfx="blush", secondary_mood="proud")
    assert renderer.mood == "happy"
    assert renderer.intensity == 3
    assert renderer.vfx == "blush"
    assert renderer.secondary_mood == "proud"

    # Test talking
    renderer.start_talking(duration_ms=200)
    assert renderer.is_talking is True
    renderer.stop_talking()
    assert renderer.is_talking is False

    # Test blinking
    renderer.blink()
    assert renderer.is_blinking is True

def test_desktop_pet_layered_renderer_integration():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        from PySide6.QtWidgets import QApplication
    from scripts.desktop_companion import DesktopPet

    app = QApplication.instance() or QApplication([])
    pet = DesktopPet()
    assert hasattr(pet, "avatar")
    assert hasattr(pet.avatar, "set_mood")

    # Set mood through DesktopPet
    pet.set_mood("glitch", intensity=2, vfx="sparks")
    assert pet.avatar.mood == "glitch"
    assert pet.avatar.intensity == 2

    # Test start_talking through DesktopPet
    pet.start_talking(300)
    assert pet.avatar.is_talking is True
    pet.stop_talking()
    assert pet.avatar.is_talking is False
