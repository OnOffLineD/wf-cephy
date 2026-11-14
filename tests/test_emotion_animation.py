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

def _make_renderer():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        from PySide6.QtWidgets import QApplication
    from scripts.layered_pet_renderer import LayeredPetRenderer

    app = QApplication.instance() or QApplication([])
    renderer = LayeredPetRenderer()
    renderer.bounce_timer.stop()
    return app, renderer

def test_hand_offsets_differ_left_right():
    app, renderer = _make_renderer()
    renderer.set_mood("idle")
    for tick in (5, 17, 40, 123):
        offsets = renderer._compute_hand_offsets(tick)
        (lx, ly), (rx, ry) = offsets["left"], offsets["right"]
        assert ly != pytest.approx(ry)
    # No talking / no glitch -> deterministic
    assert renderer._compute_hand_offsets(17) == renderer._compute_hand_offsets(17)
    # Painting with independent transforms must not crash
    assert not renderer.grab().isNull()

def test_talking_gesture_offset_active():
    app, renderer = _make_renderer()
    renderer.set_mood("idle")
    base = renderer._compute_hand_offsets(30)
    assert renderer._compute_gesture_offset() == 0.0

    renderer.start_talking()
    for _ in range(3):
        renderer._on_bounce_tick()
    assert renderer.talk_tick == 3
    gesture = renderer._compute_gesture_offset()
    assert abs(gesture) > 1.0
    talking = renderer._compute_hand_offsets(30)
    assert talking["right"][1] == pytest.approx(base["right"][1] + gesture)
    assert talking["left"] == base["left"]
    assert not renderer.grab().isNull()

    renderer.stop_talking()
    assert renderer._compute_gesture_offset() == 0.0

def test_glitch_jitter_offset():
    app, renderer = _make_renderer()
    renderer.set_mood("idle")
    assert renderer._compute_jitter() == (0, 0)

    renderer.set_mood("glitch")
    jitters = [renderer._compute_jitter() for _ in range(50)]
    assert all(-2 <= jx <= 2 and -2 <= jy <= 2 for jx, jy in jitters)
    assert any(j != (0, 0) for j in jitters)
    hand_samples = {renderer._compute_hand_offsets(10)["left"] for _ in range(50)}
    assert len(hand_samples) > 1
    assert not renderer.grab().isNull()

def _face_center(renderer):
    c = renderer.body_rect().center()
    return float(c.x()), float(c.y()) - 8.0

def _in_eye_ellipse(renderer, x, y):
    return (x / renderer.MAX_EYE_OFFSET_X) ** 2 + (y / renderer.MAX_EYE_OFFSET_Y) ** 2 <= 1.0 + 1e-6

def test_eye_target_tracks_cursor_direction():
    from scripts.layered_pet_renderer import QPointF
    app, renderer = _make_renderer()
    fx, fy = _face_center(renderer)
    tx, ty = renderer.update_eye_target(QPointF(fx + 100, fy + 60), is_local=True)
    assert tx > 0 and ty > 0
    assert (tx, ty) == (renderer.eye_target_x, renderer.eye_target_y)
    assert _in_eye_ellipse(renderer, tx, ty)
    for dx, dy, sx, sy in ((-80, 0, -1, 0), (80, 0, 1, 0), (0, -80, 0, -1), (0, 80, 0, 1)):
        tx, ty = renderer.update_eye_target(QPointF(fx + dx, fy + dy), is_local=True)
        assert (tx > 0) - (tx < 0) == sx
        assert (ty > 0) - (ty < 0) == sy
    # Manual local cursor persists across ticks (no live cursor override)
    renderer.update_eye_target()
    assert renderer.eye_target_y > 0 and renderer.eye_target_x == pytest.approx(0.0)

def test_eye_offset_lerps_gradually_and_converges():
    from scripts.layered_pet_renderer import QPointF
    app, renderer = _make_renderer()
    fx, fy = _face_center(renderer)
    tx, ty = renderer.update_eye_target(QPointF(fx + 100, fy + 60), is_local=True)
    renderer._step_motion()
    assert renderer.eye_offset_x == pytest.approx(tx * renderer.EYE_LERP_FACTOR)
    assert renderer.eye_offset_y == pytest.approx(ty * renderer.EYE_LERP_FACTOR)
    assert 0 < renderer.eye_offset_x < tx and 0 < renderer.eye_offset_y < ty
    prev = renderer.eye_offset_x
    for _ in range(80):
        renderer._step_motion()
        assert renderer.eye_offset_x >= prev
        prev = renderer.eye_offset_x
    assert renderer.eye_offset_x == pytest.approx(tx)
    assert renderer.eye_offset_y == pytest.approx(ty)

def test_eye_offset_clamped_to_face_ellipse_and_renders():
    from scripts.layered_pet_renderer import QPointF
    app, renderer = _make_renderer()
    assert _in_eye_ellipse(renderer, *renderer._clamp_eye_offset(100.0, -100.0))
    for pt in ((10000, -10000), (-5000, 8000)):
        tx, ty = renderer.update_eye_target(QPointF(*pt), is_local=True)
        assert _in_eye_ellipse(renderer, tx, ty)
        for _ in range(60):
            renderer._step_motion()
            assert _in_eye_ellipse(renderer, renderer.eye_offset_x, renderer.eye_offset_y)
        assert not renderer.grab().isNull()
    # Procedural chibi fallback with eye offset applied
    renderer.has_layers = False
    renderer.asset_dir = os.path.join(renderer.asset_dir, "__missing__")
    renderer._cache.clear()
    assert renderer.eye_offset_x != 0.0
    assert not renderer.grab().isNull()

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
