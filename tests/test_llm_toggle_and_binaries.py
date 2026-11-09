import io
import os
import sys
import zipfile
from unittest.mock import MagicMock, patch

import pytest
import requests

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from scripts import embedded_llm_runner as elr
from scripts.embedded_llm_runner import EmbeddedLLMRunner
from scripts.persona_manager import PersonaManager

URL = "http://example/llama.zip"


def test_llm_enabled_defaults_true_and_persists(tmp_path):
    cfg = str(tmp_path / "persona.json")
    pm = PersonaManager(config_path=cfg)
    assert pm.get_llm_enabled() is True
    pm.set_llm_enabled(False)
    assert PersonaManager(config_path=cfg).get_llm_enabled() is False


def _runner(tmp_path):
    runner = EmbeddedLLMRunner(model_path=str(tmp_path / "models" / "m.gguf"))
    runner.bin_path = str(tmp_path / "bin" / "llama-server.exe")
    return runner


def _response(payload):
    response = MagicMock(headers={"content-length": str(len(payload))})
    response.iter_content.return_value = [payload]
    return response


def test_ensure_binaries_exist_downloads_only_when_missing(tmp_path):
    runner = _runner(tmp_path)
    with patch.object(runner, "download_binaries", return_value=True) as download:
        assert runner.ensure_binaries_exist() is True
        os.makedirs(os.path.dirname(runner.bin_path))
        open(runner.bin_path, "wb").close()
        assert runner.ensure_binaries_exist() is True
    download.assert_called_once()


def test_download_binaries_extracts_zip_flat_into_bin(tmp_path):
    runner = _runner(tmp_path)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("build/bin/llama-server.exe", b"exe")
        archive.writestr("../evil.dll", b"x")
    with patch.object(runner, "_resolve_bin_url", return_value=URL), \
            patch("scripts.embedded_llm_runner.requests.get", return_value=_response(buf.getvalue())) as get:
        assert runner.download_binaries() is True
    assert get.call_args.kwargs["stream"] is True
    assert (tmp_path / "bin" / "llama-server.exe").read_bytes() == b"exe"
    assert not (tmp_path / "evil.dll").exists()
    assert not any(p.name.endswith(".tmp") for p in (tmp_path / "bin").iterdir())


def test_download_binaries_failure_reports_and_cleans_up(tmp_path):
    runner = _runner(tmp_path)
    with patch.object(runner, "_resolve_bin_url", return_value=URL), \
            patch("scripts.embedded_llm_runner.requests.get", return_value=_response(b"not a zip")):
        assert runner.download_binaries() is False
    assert "다운로드 실패" in runner.last_error
    assert list((tmp_path / "bin").iterdir()) == []


def test_resolve_bin_url_prefers_latest_cpu_asset_else_pinned():
    runner = EmbeddedLLMRunner()
    with patch("scripts.embedded_llm_runner.requests.get", side_effect=requests.ConnectionError()):
        assert runner._resolve_bin_url() == elr.LLAMA_BIN_URL
    latest = MagicMock()
    latest.json.return_value = {"assets": [
        {"name": "llama-b9999-bin-win-cuda-x64.zip", "browser_download_url": "cuda"},
        {"name": f"llama-b9999-{elr.LLAMA_BIN_ASSET_SUFFIX}", "browser_download_url": "cpu"}]}
    with patch("scripts.embedded_llm_runner.requests.get", return_value=latest):
        assert runner._resolve_bin_url() == "cpu"


def test_start_server_never_downloads_binaries(tmp_path):
    runner = _runner(tmp_path)
    runner.is_healthy = MagicMock(return_value=False)
    with patch.object(runner, "download_binaries") as download:
        assert runner.start_server(wait_ready=False) is False
    download.assert_not_called()
    assert "--download-bin" in runner.last_error


@pytest.mark.parametrize("flags, want_bin, want_model, ok, code", [
    (["--download-bin"], True, False, True, 0),
    (["--download-model"], False, True, True, 0),
    (["--download"], False, True, True, 0),  # legacy: model only
    (["--download-bin", "--download-model"], True, True, True, 0),  # what start_companion.bat runs
    (["--download-bin"], True, False, False, 1),
])
def test_cli_download_flags(flags, want_bin, want_model, ok, code):
    with patch.object(EmbeddedLLMRunner, "ensure_binaries_exist", return_value=ok) as bins, \
            patch.object(EmbeddedLLMRunner, "ensure_model_exists", return_value=ok) as model, \
            patch.object(sys, "argv", ["embedded_llm_runner.py", *flags]), \
            pytest.raises(SystemExit) as exit_info:
        elr.main()
    assert (exit_info.value.code, bins.called, model.called) == (code, want_bin, want_model)


def test_companion_cli_flags_update_persona(tmp_path):
    from scripts.desktop_companion import apply_llm_cli_flags
    pm = PersonaManager(config_path=str(tmp_path / "persona.json"))
    apply_llm_cli_flags(pm, ["main_companion.py", "--disable-llm"])
    assert pm.get_llm_enabled() is False
    apply_llm_cli_flags(pm, ["main_companion.py", "--enable-llm"])
    assert pm.get_llm_enabled() is True


@pytest.fixture(scope="module")
def qapp():
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        from PySide6.QtWidgets import QApplication
    # Held by the fixture: an unreferenced QApplication is collected and crashes the widgets.
    return QApplication.instance() or QApplication([])


@pytest.fixture
def panel(qapp, tmp_path, monkeypatch):
    from scripts.desktop_companion import OrdisCompanionApp
    monkeypatch.setattr(OrdisCompanionApp, "refresh_world_events", lambda self: None)
    app = OrdisCompanionApp()
    # Isolated config: never touch the user's real persona_config.json.
    app.orchestrator.persona_manager = PersonaManager(config_path=str(tmp_path / "persona.json"))
    app.llm_runner.start_server = MagicMock(return_value=True)
    app.llm_runner.stop_server = MagicMock()
    app.messages = []
    app.chat_reply_signal.connect(lambda sender, text, *rest: app.messages.append(text))
    yield app
    app.close()


def _run_start(panel, **kwargs):
    with patch("scripts.desktop_companion.threading") as threading_mod:
        panel.start_llm_in_background(**kwargs)
    if threading_mod.Thread.called:
        threading_mod.Thread.call_args.kwargs["target"]()
    return threading_mod.Thread.called


def test_disabled_llm_skips_server_launch(panel):
    panel.orchestrator.persona_manager.set_llm_enabled(False)
    assert _run_start(panel) is False
    panel.llm_runner.start_server.assert_not_called()
    assert any("로컬 LLM이 비활성화 상태입니다" in m for m in panel.messages)


def test_enabled_llm_starts_server(panel):
    assert _run_start(panel) is True
    panel.llm_runner.start_server.assert_called_once()


def test_toggle_on_fetches_binaries_before_start(panel):
    panel.llm_runner.ensure_binaries_exist = MagicMock(return_value=False)
    panel.llm_runner.last_error = "llama-server 다운로드 실패: offline"
    _run_start(panel, download_binaries=True)
    panel.llm_runner.start_server.assert_not_called()
    assert any("offline" in m for m in panel.messages)


def test_settings_toggle_off_stops_server_and_on_restarts(panel, monkeypatch):
    from scripts.desktop_companion import QDialog
    texts, state = [], {}

    class FakeDialog:
        def __init__(self, pm, parent=None):
            self.pm = pm

        def exec(self):
            self.pm.set_llm_enabled(state["enabled"])
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr("scripts.desktop_companion.OrdisPersonaDialog", FakeDialog)
    monkeypatch.setattr(panel, "add_chat_bubble", lambda sender, text, **kw: texts.append(text))
    panel.start_llm_in_background = MagicMock()

    state["enabled"] = False
    panel.open_settings_dialog()
    panel.llm_runner.stop_server.assert_called_once()
    panel.start_llm_in_background.assert_not_called()
    assert any("VRAM이 반환되었습니다" in t for t in texts)

    state["enabled"] = True
    panel.open_settings_dialog()
    panel.start_llm_in_background.assert_called_once_with(download_binaries=True)
    panel.llm_runner.stop_server.assert_called_once()


def test_persona_dialog_binds_llm_checkbox(qapp, tmp_path):
    from scripts.persona_dialog import OrdisPersonaDialog
    pm = PersonaManager(config_path=str(tmp_path / "persona.json"))
    pm.set_llm_enabled(False)
    dlg = OrdisPersonaDialog(persona_manager=pm)
    assert dlg.cb_llm_enabled.isChecked() is False
    dlg.cb_llm_enabled.setChecked(True)
    dlg.save()
    assert pm.get_llm_enabled() is True
