import os
import tempfile
import pytest
from scripts.persona_manager import PersonaManager, DEFAULT_PRESETS
from scripts.llm_orchestrator import LLMOrchestrator

def test_persona_manager_defaults():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = os.path.join(tmpdir, "test_persona.json")
        pm = PersonaManager(config_path=cfg_path)
        assert pm.get_mode() == "random"
        presets = pm.get_presets()
        assert "caretaker" in presets
        assert "glitch" in presets
        assert "tactical" in presets

def test_persona_manager_modes_and_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = os.path.join(tmpdir, "test_persona.json")
        pm = PersonaManager(config_path=cfg_path)
        
        # Test caretaker fixed mode
        pm.set_mode("caretaker")
        assert pm.get_mode() == "caretaker"
        active = pm.get_active_persona()
        assert active["id"] == "caretaker"
        assert active["name"] == "충성스러운 집사"
        assert "안전" in active["prompt"]

        # Test glitch fixed mode
        pm.set_mode("glitch")
        assert pm.get_mode() == "glitch"
        active = pm.get_active_persona()
        assert active["id"] == "glitch"
        assert active["name"] == "욱하는 글리치"

        # Test tactical fixed mode
        pm.set_mode("tactical")
        assert pm.get_mode() == "tactical"
        active = pm.get_active_persona()
        assert active["id"] == "tactical"
        assert active["name"] == "냉철한 전술장교"

        # Test custom prompt mode
        pm.set_mode("custom", "오퍼레이터에게 츤데레 말투로 대답하세요.")
        assert pm.get_mode() == "custom"
        assert pm.get_custom_prompt() == "오퍼레이터에게 츤데레 말투로 대답하세요."
        active = pm.get_active_persona()
        assert active["id"] == "custom"
        assert "츤데레" in active["prompt"]

        # Re-load from file to verify persistence
        pm2 = PersonaManager(config_path=cfg_path)
        assert pm2.get_mode() == "custom"
        assert pm2.get_custom_prompt() == "오퍼레이터에게 츤데레 말투로 대답하세요."

def test_persona_manager_random_mode():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = os.path.join(tmpdir, "test_persona.json")
        pm = PersonaManager(config_path=cfg_path)
        pm.set_mode("random")
        assert pm.get_mode() == "random"
        active = pm.get_active_persona()
        assert active["id"] in ["caretaker", "glitch", "tactical"]
        assert "랜덤" in active["name"]

def test_orchestrator_integration():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = os.path.join(tmpdir, "test_persona.json")
        orch = LLMOrchestrator()
        orch.persona_manager = PersonaManager(config_path=cfg_path)
        
        # Fast status check bypass
        res = orch.chat_smalltalk("작동중?")
        assert "정상" in res or "오디스" in res

        # Check persona prompt lookup
        orch.persona_manager.set_mode("tactical")
        p = orch.persona_manager.get_active_persona()
        assert p["id"] == "tactical"

def test_persona_dialog_headless():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        from PySide6.QtWidgets import QApplication
    from scripts.persona_dialog import OrdisPersonaDialog

    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = os.path.join(tmpdir, "test_persona.json")
        pm = PersonaManager(config_path=cfg_path)
        pm.set_mode("tactical")
        
        dlg = OrdisPersonaDialog(persona_manager=pm)
        assert dlg.radio_tactical.isChecked() is True
        assert "전술장교" in dlg.lbl_preview.text()

        # Switch to custom
        dlg.radio_custom.setChecked(True)
        assert dlg.edit_custom.isEnabled() is True
        dlg.edit_custom.setText("테스트 커스텀 프롬프트")
        dlg.save()

        assert pm.get_mode() == "custom"
        assert pm.get_custom_prompt() == "테스트 커스텀 프롬프트"
