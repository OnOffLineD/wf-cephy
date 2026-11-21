"""Ollama / hosted API engines next to the bundled llama.cpp server."""
import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest
import requests

from scripts.llm_orchestrator import CHAT_MOOD_GRAMMAR, INTENT_GRAMMAR, LLMOrchestrator
from scripts.llm_providers import (
    ApiKeyStore, LLMClient, clean_reply, default_base_url, extract_json_object, tool_call_schema,
)
from scripts.persona_manager import PersonaManager


def _response(status=200, payload=None):
    res = MagicMock(status_code=status)
    res.json.return_value = payload if payload is not None else {}
    res.text = json.dumps(payload or {})
    return res


def _openai_reply(text):
    return _response(200, {"choices": [{"message": {"content": text}}]})


# --------------------------------------------------------------- wire formats

def test_openai_request_carries_key_and_model_but_no_grammar_or_cap():
    client = LLMClient("openai", api_key="sk-test", model="gpt-5-mini")
    with patch("scripts.llm_providers.requests.post", return_value=_openai_reply("[MOOD:happy:1] 안녕")) as post:
        assert client.complete("sys", "hi", temperature=0.3, grammar=CHAT_MOOD_GRAMMAR, max_tokens=4) == "[MOOD:happy:1] 안녕"
    url, kwargs = post.call_args.args[0], post.call_args.kwargs
    assert url == "https://api.openai.com/v1/chat/completions"
    assert kwargs["headers"]["Authorization"] == "Bearer sk-test"
    body = kwargs["json"]
    assert body["model"] == "gpt-5-mini" and body["temperature"] == 0.3
    assert body["messages"] == [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}]
    # GBNF is llama.cpp-only, and a small cap leaves a reasoning model with no answer.
    assert "grammar" not in body and "max_tokens" not in body


def test_openai_reasoning_model_is_retried_without_temperature():
    client = LLMClient("openai", api_key="k")
    rejected = _response(400, {"error": {"message": "Unsupported value: 'temperature'"}})
    with patch("scripts.llm_providers.requests.post", side_effect=[rejected, _openai_reply("OK")]) as post:
        assert client.complete("s", "u", temperature=0.2) == "OK"
    assert "temperature" in post.call_args_list[0].kwargs["json"]
    assert "temperature" not in post.call_args_list[1].kwargs["json"]


def test_anthropic_request_shape_and_text_blocks():
    client = LLMClient("anthropic", api_key="sk-ant", base_url="https://api.anthropic.com/v1")
    reply = _response(200, {"content": [{"type": "thinking", "thinking": "..."},
                                        {"type": "text", "text": "[MOOD:proud:2] "}, {"type": "text", "text": "완료"}]})
    with patch("scripts.llm_providers.requests.post", return_value=reply) as post:
        assert client.complete("시스템", "질문", temperature=0.6) == "[MOOD:proud:2] 완료"
    assert post.call_args.args[0] == "https://api.anthropic.com/v1/messages"
    headers, body = post.call_args.kwargs["headers"], post.call_args.kwargs["json"]
    assert headers["x-api-key"] == "sk-ant" and headers["anthropic-version"]
    assert body["system"] == "시스템" and body["messages"] == [{"role": "user", "content": "질문"}]
    assert body["max_tokens"] > 0 and body["model"].startswith("claude-")


def test_ollama_uses_native_chat_with_schema_and_context_size():
    client = LLMClient("ollama", model="gemma3:4b", context_size=8192)
    schema = {"type": "object"}
    reply = _response(200, {"message": {"role": "assistant", "content": "<think>음...</think>{\"label\": \"TODO\"}"}})
    with patch("scripts.llm_providers.requests.post", return_value=reply) as post:
        assert client.complete("s", "u", temperature=0.0, grammar=INTENT_GRAMMAR, json_schema=schema) == '{"label": "TODO"}'
    assert post.call_args.args[0].endswith("/api/chat")
    body = post.call_args.kwargs["json"]
    assert body["format"] == schema and body["options"]["num_ctx"] == 8192 and body["stream"] is False
    assert "grammar" not in body and "Authorization" not in post.call_args.kwargs["headers"]


def test_remote_ollama_sends_its_api_key_as_bearer():
    client = LLMClient("ollama", base_url="https://ollama.example.com/", api_key="ol-secret", model="gemma3:4b")
    with patch("scripts.llm_providers.requests.get", return_value=_response(200, {"models": [{"name": "gemma3:4b"}]})) as get, \
            patch("scripts.llm_providers.requests.post", return_value=_response(200, {"message": {"content": "OK"}})) as post:
        assert client.test_connection()[0] is True
    assert get.call_args.args[0] == "https://ollama.example.com/api/tags"
    assert post.call_args.args[0] == "https://ollama.example.com/api/chat"
    for call in (get.call_args, post.call_args):
        assert call.kwargs["headers"]["Authorization"] == "Bearer ol-secret"


def test_remote_ollama_rejecting_the_key_says_so():
    client = LLMClient("ollama", base_url="https://ollama.example.com", api_key="wrong")
    with patch("scripts.llm_providers.requests.get", return_value=_response(401, {"error": "unauthorized"})):
        ok, message = client.check_ready()
    assert not ok and "API 키가 거부" in message


def test_llamacpp_payload_keeps_grammar_cap_and_given_url():
    client = LLMClient()
    with patch("scripts.llm_providers.requests.post", return_value=_openai_reply(" GUIDE ")) as post:
        assert client.complete("s", "u", temperature=0.0, grammar=INTENT_GRAMMAR, max_tokens=4, timeout=5,
                               url="http://127.0.0.1:9/v1/chat/completions") == "GUIDE"
    assert post.call_args.args[0] == "http://127.0.0.1:9/v1/chat/completions"
    assert post.call_args.kwargs["timeout"] == 5
    assert post.call_args.kwargs["json"]["grammar"] == INTENT_GRAMMAR and post.call_args.kwargs["json"]["max_tokens"] == 4


def test_missing_key_fails_without_a_request():
    client = LLMClient("gemini")
    with patch("scripts.llm_providers.requests.post") as post:
        assert client.complete("s", "u") is None
    post.assert_not_called()
    assert "API 키" in client.last_error


@pytest.mark.parametrize("status, payload, words", [
    (401, {"error": {"message": "Incorrect API key"}}, ("API 키가 거부", "Incorrect API key")),
    (429, [{"error": {"message": "quota"}}], ("한도", "quota")),
    (404, {"error": "model 'x' not found"}, ("찾을 수 없", "not found")),
])
def test_http_errors_are_explained(status, payload, words):
    client = LLMClient("openai", api_key="k")
    with patch("scripts.llm_providers.requests.post", return_value=_response(status, payload)):
        assert client.complete("s", "u") is None
    assert all(w in client.last_error for w in words)


def test_network_failure_is_reported_not_raised():
    client = LLMClient("ollama")
    with patch("scripts.llm_providers.requests.post", side_effect=requests.ConnectionError()):
        assert client.complete("s", "u") is None
    assert "연결할 수 없습니다" in client.last_error


def test_reply_cleanup_and_json_extraction():
    assert clean_reply("<think>계산 중</think>\n답입니다") == "답입니다"
    assert clean_reply("<think>끝나지 않은 생각") == ""
    assert extract_json_object('```json\n{"tool": "add_todo", "args": {"task": "출격"}}\n```') == \
        {"tool": "add_todo", "args": {"task": "출격"}}
    assert extract_json_object('도구를 골랐습니다: {"tool": "x", "args": {}} 입니다') == {"tool": "x", "args": {}}
    assert extract_json_object("JSON 아님") is None and extract_json_object("[1, 2]") is None


def test_tool_schema_requires_shared_args_only():
    todo = tool_call_schema({"add_todo": {"args": ["task"]}, "delete_todo": {"args": ["task"]}})
    assert todo["properties"]["tool"]["enum"] == ["add_todo", "delete_todo"]
    assert todo["properties"]["args"]["required"] == ["task"]
    guide = tool_call_schema({"search_wiki": {"args": ["query"]}, "lookup_drop": {"args": ["item"]}})
    assert set(guide["properties"]["args"]["properties"]) == {"query", "item"}
    assert "required" not in guide["properties"]["args"]


@pytest.mark.parametrize("env, expected", [
    ("", "http://localhost:11434"), ("0.0.0.0", "http://127.0.0.1:11434"),
    ("192.168.0.5:9999", "http://192.168.0.5:9999"), ("https://ollama.lan", "https://ollama.lan:11434"),
])
def test_ollama_address_follows_ollama_host(monkeypatch, env, expected):
    monkeypatch.setenv("OLLAMA_HOST", env)
    assert default_base_url("ollama") == expected


# ------------------------------------------------------------------- checks

def test_ollama_check_names_the_pull_command_for_a_missing_model():
    client = LLMClient("ollama", model="exaone3.5:7.8b")
    with patch("scripts.llm_providers.requests.get", return_value=_response(200, {"models": [{"name": "gemma3:4b"}]})):
        ok, message = client.check_ready()
    assert not ok and "ollama pull exaone3.5:7.8b" in message and "gemma3:4b" in message
    with patch("scripts.llm_providers.requests.get", return_value=_response(200, {"models": [{"name": "exaone3.5:latest"}]})):
        assert LLMClient("ollama", model="exaone3.5").check_ready() == (True, "")


def test_gemini_model_list_matches_without_models_prefix():
    client = LLMClient("gemini", api_key="k")
    listing = _response(200, {"data": [{"id": "models/gemini-2.5-flash"}]})
    with patch("scripts.llm_providers.requests.get", return_value=listing) as get:
        assert client.check_ready() == (True, "")
    assert get.call_args.args[0].endswith("/v1beta/openai/models")
    with patch("scripts.llm_providers.requests.get", return_value=listing):
        ok, message = LLMClient("gemini", api_key="k", model="gemini-typo").check_ready()
    assert ok and "gemini-typo" in message


def test_bad_key_fails_the_free_check():
    with patch("scripts.llm_providers.requests.get", return_value=_response(401, {"error": {"message": "bad key"}})):
        ok, message = LLMClient("openai", api_key="wrong").check_ready()
    assert not ok and "API 키가 거부" in message


# --------------------------------------------------------------------- keys

def test_key_store_seals_keys_and_falls_back_to_env(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    path = tmp_path / "api_keys.json"
    store = ApiKeyStore(str(path))
    assert store.get("openai") == ""
    store.set("openai", "  sk-secret-123  ")
    assert "sk-secret-123" not in path.read_text(encoding="utf-8")
    assert ApiKeyStore(str(path)).get("openai") == "sk-secret-123"
    if sys.platform == "win32":
        assert json.loads(path.read_text(encoding="utf-8"))["openai"].startswith("dpapi:")

    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")
    assert store.get("openai") == "sk-secret-123"  # the key typed in settings wins
    store.set("openai", "")
    assert "openai" not in json.loads(path.read_text(encoding="utf-8"))
    assert store.get("openai") == "sk-from-env" and store.env_name("openai") == "OPENAI_API_KEY"


def test_key_sealed_elsewhere_reads_as_missing(tmp_path):
    path = tmp_path / "api_keys.json"
    path.write_text(json.dumps({"openai": "dpapi:bm90LWEtcmVhbC1ibG9i", "gemini": "???"}), encoding="utf-8")
    store = ApiKeyStore(str(path))
    assert store.saved("openai") == "" and store.saved("gemini") == ""


# ----------------------------------------------------------------- settings

def test_provider_settings_persist_per_provider_without_pinning_defaults(tmp_path):
    cfg = str(tmp_path / "persona.json")
    pm = PersonaManager(config_path=cfg)
    assert pm.get_llm_provider() == "local"
    pm.set_llm_provider("nonsense")
    assert pm.get_llm_provider() == "local"

    pm.set_llm_provider("ollama")
    pm.set_llm_model("ollama", "qwen3:8b")
    pm.set_llm_base_url("ollama", "http://10.0.0.2:11434/")
    pm.set_llm_model("openai", "gpt-5-mini")  # the preset default
    pm.set_llm_base_url("openai", "https://api.openai.com/v1")

    again = PersonaManager(config_path=cfg)
    assert again.get_llm_provider() == "ollama"
    assert again.get_llm_model() == "qwen3:8b" and again.get_llm_base_url() == "http://10.0.0.2:11434"
    raw = json.loads(open(cfg, encoding="utf-8").read())
    assert "openai" not in raw.get("llm_models", {}) and "openai" not in raw.get("llm_base_urls", {})


# ------------------------------------------------------------- orchestrator

@pytest.fixture(scope="module")
def shared_orc():
    return LLMOrchestrator()


@pytest.fixture
def remote_orc(shared_orc, tmp_path):
    """The shared orchestrator switched to a hosted engine with its own settings and key file."""
    pm = PersonaManager(config_path=str(tmp_path / "persona.json"))
    pm.set_llm_provider("openai")
    keys = ApiKeyStore(str(tmp_path / "keys.json"))
    keys.set("openai", "sk-test")
    saved = shared_orc.persona_manager, shared_orc.api_keys, shared_orc.runner
    shared_orc.persona_manager, shared_orc.api_keys = pm, keys
    shared_orc.runner = MagicMock()
    # A bundled engine that is down must not block a hosted one.
    shared_orc.runner.is_starting.return_value = True
    shared_orc.runner.is_healthy.return_value = False
    shared_orc.reload_llm_settings()
    yield shared_orc
    shared_orc.persona_manager, shared_orc.api_keys, shared_orc.runner = saved
    shared_orc.reload_llm_settings()


def test_hosted_engine_answers_while_local_runner_is_down(remote_orc):
    assert remote_orc.llm_loading() is False
    with patch("scripts.llm_providers.requests.post", return_value=_openai_reply("[MOOD:happy:1] 네")) as post:
        assert remote_orc._call_llm("sys", "안녕") == "[MOOD:happy:1] 네"
    assert post.call_args.args[0] == "https://api.openai.com/v1/chat/completions"
    assert post.call_args.kwargs["headers"]["Authorization"] == "Bearer sk-test"


def test_master_switch_off_skips_hosted_engine(remote_orc):
    remote_orc.persona_manager.set_llm_enabled(False)
    with patch("scripts.llm_providers.requests.post") as post:
        assert remote_orc._call_llm("sys", "안녕") is None
    post.assert_not_called()


@pytest.mark.parametrize("content, expected", [("TODO 입니다", "TODO"), ('{"label": "GUIDE"}', "GUIDE"), ("모르겠어요", "SMALLTALK")])
def test_hosted_intent_label_is_found_inside_extra_words(remote_orc, content, expected):
    with patch("scripts.llm_providers.requests.post", return_value=_openai_reply(content)) as post:
        assert remote_orc.classify_intent("이따가 저녁 먹고 나서 뭐 좀 챙겨볼까?", rag_top_score=0.0) == expected
    assert "grammar" not in post.call_args.kwargs["json"]


def test_hosted_tool_call_is_parsed_from_fenced_json(remote_orc):
    reply = _openai_reply('```json\n{"tool": "complete_todo", "args": {"task": "출격"}}\n```')
    with patch("scripts.llm_providers.requests.post", return_value=reply) as post:
        assert remote_orc.resolve_domain_tool("TODO", "오늘 출격 끝냈어") == {"tool": "complete_todo", "args": {"task": "출격"}}
    assert "JSON 한 줄만" in post.call_args.kwargs["json"]["messages"][0]["content"]


@pytest.mark.parametrize("content", [
    '{"tool": "complete_todo", "args": {"task": "' + "가" * 41 + '"}}',  # longer than the grammar allows locally
    '{"tool": "search_wiki", "args": {"query": "출격"}}',  # a tool from another domain
    '{"tool": ["complete_todo"], "args": {"task": "출격"}}',
    '{"tool": "complete_todo", "args": {"task": "   "}}',
])
def test_hosted_tool_call_is_held_to_the_local_limits(remote_orc, content):
    with patch("scripts.llm_providers.requests.post", return_value=_openai_reply(content)):
        assert remote_orc.resolve_domain_tool("TODO", "오늘 출격 끝냈어") is None


def test_context_command_does_not_start_local_engine_for_hosted(remote_orc):
    remote_orc.set_context_mode("8k")
    remote_orc.runner.restart_server.assert_not_called()
    assert remote_orc.llm_client.context_size == 8192
    remote_orc.set_context_mode("4k")


# ---------------------------------------------------------------- dialog / app

@pytest.fixture
def qapp():
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_dialog_saves_remote_ollama_address_and_key(qapp, tmp_path, monkeypatch):
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    from scripts.persona_dialog import OrdisPersonaDialog
    pm = PersonaManager(config_path=str(tmp_path / "persona.json"))
    keys = ApiKeyStore(str(tmp_path / "keys.json"))
    dlg = OrdisPersonaDialog(persona_manager=pm, api_keys=keys)
    dlg.provider_combo.setCurrentIndex(dlg.provider_combo.findData("ollama"))
    assert dlg.api_key_edit.isEnabled() and "Bearer" in dlg.api_key_edit.placeholderText()
    dlg.base_url_edit.setText("https://ollama.example.com")
    dlg.api_key_edit.setText("ol-secret")
    dlg.save()
    assert pm.get_llm_base_url("ollama") == "https://ollama.example.com"
    assert keys.get("ollama") == "ol-secret"
    client = LLMOrchestrator.__new__(LLMOrchestrator)
    client.persona_manager, client.api_keys = pm, keys
    assert client.reload_llm_settings().api_key == "ol-secret"


def test_dialog_switches_sections_and_saves_key_outside_persona_config(qapp, tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from scripts.persona_dialog import OrdisPersonaDialog
    cfg = tmp_path / "persona.json"
    pm = PersonaManager(config_path=str(cfg))
    keys = ApiKeyStore(str(tmp_path / "keys.json"))
    dlg = OrdisPersonaDialog(persona_manager=pm, api_keys=keys)
    assert dlg.remote_box.isHidden() and not dlg.local_model_box.isHidden()

    dlg.provider_combo.setCurrentIndex(dlg.provider_combo.findData("ollama"))
    assert not dlg.remote_box.isHidden() and dlg.local_model_box.isHidden() and dlg.gpu_box.isHidden()
    assert not dlg.context_box.isHidden()

    dlg.provider_combo.setCurrentIndex(dlg.provider_combo.findData("anthropic"))
    assert dlg.context_box.isHidden() and dlg.api_key_edit.isEnabled()
    dlg.remote_model_combo.setCurrentText("claude-sonnet-5-5")
    dlg.api_key_edit.setText("sk-ant-secret")
    # Typing survives a detour through another engine.
    dlg.provider_combo.setCurrentIndex(dlg.provider_combo.findData("openai"))
    dlg.provider_combo.setCurrentIndex(dlg.provider_combo.findData("anthropic"))
    assert dlg.api_key_edit.text() == "sk-ant-secret"
    dlg.save()

    again = PersonaManager(config_path=str(cfg))
    assert again.get_llm_provider() == "anthropic" and again.get_llm_model() == "claude-sonnet-5-5"
    assert keys.get("anthropic") == "sk-ant-secret"
    assert "sk-ant-secret" not in cfg.read_text(encoding="utf-8")


def test_dialog_connection_test_reports_and_fills_ollama_models(qapp, tmp_path):
    from scripts.persona_dialog import OrdisPersonaDialog
    pm = PersonaManager(config_path=str(tmp_path / "persona.json"))
    pm.set_llm_provider("ollama")
    dlg = OrdisPersonaDialog(persona_manager=pm, api_keys=ApiKeyStore(str(tmp_path / "keys.json")))
    tags = _response(200, {"models": [{"name": "gemma3:4b"}, {"name": "qwen3:8b"}]})
    chat = _response(200, {"message": {"content": "OK"}})
    with patch("scripts.persona_dialog.threading.Thread") as thread, \
            patch("scripts.llm_providers.requests.get", return_value=tags), \
            patch("scripts.llm_providers.requests.post", return_value=chat):
        dlg.btn_test_connection.click()
        assert not dlg.btn_test_connection.isEnabled()
        thread.call_args.kwargs["target"]()
    qapp.processEvents()
    assert dlg.btn_test_connection.isEnabled()
    assert "연결 성공" in dlg.lbl_connection_status.text()
    assert [dlg.remote_model_combo.itemText(i) for i in range(dlg.remote_model_combo.count())] == ["gemma3:4b", "qwen3:8b"]
    assert dlg.remote_model_combo.currentText() == "gemma3:4b"


@pytest.fixture
def panel(qapp, tmp_path, monkeypatch):
    from scripts.desktop_companion import OrdisCompanionApp
    monkeypatch.setattr(OrdisCompanionApp, "refresh_world_events", lambda self: None)
    app = OrdisCompanionApp()
    app.orchestrator.persona_manager = PersonaManager(config_path=str(tmp_path / "persona.json"))
    app.orchestrator.api_keys = ApiKeyStore(str(tmp_path / "keys.json"))
    app.llm_runner.start_server = MagicMock(return_value=True)
    app.llm_runner.stop_server = MagicMock()
    app.messages = []
    app.chat_reply_signal.connect(lambda sender, text, *rest: app.messages.append(text))
    yield app
    app.close()


def _run_start(panel):
    with patch("scripts.desktop_companion.threading") as threading_mod:
        panel.start_llm_in_background()
    threading_mod.Thread.call_args.kwargs["target"]()


def test_hosted_engine_start_checks_instead_of_loading_local_model(panel):
    panel.orchestrator.persona_manager.set_llm_provider("ollama")
    with patch("scripts.llm_providers.requests.get", return_value=_response(200, {"models": [{"name": "gemma3:4b"}]})):
        _run_start(panel)
    panel.llm_runner.start_server.assert_not_called()
    assert any("준비" in m and "Ollama" in m for m in panel.messages)


def test_hosted_engine_without_key_is_reported(panel, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    panel.orchestrator.persona_manager.set_llm_provider("openai")
    with patch("scripts.llm_providers.requests.get") as get:
        _run_start(panel)
    get.assert_not_called()
    assert any("연결하지 못했습니다" in m and "API 키" in m for m in panel.messages)


def test_switching_from_local_to_hosted_frees_local_engine(panel, monkeypatch):
    from scripts.desktop_companion import QDialog
    texts = []

    class FakeDialog:
        def __init__(self, pm, parent=None):
            self.pm = pm

        def exec(self):
            self.pm.set_llm_provider("ollama")
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr("scripts.desktop_companion.OrdisPersonaDialog", FakeDialog)
    monkeypatch.setattr(panel, "add_chat_bubble", lambda sender, text, **kw: texts.append(text))
    panel.start_llm_in_background = MagicMock()
    panel.open_settings_dialog()
    panel.llm_runner.stop_server.assert_called_once()
    panel.start_llm_in_background.assert_called_once_with()
    assert any("Ollama" in t and "VRAM" in t for t in texts)
    # Saving again with nothing changed neither restarts nor re-announces.
    FakeDialog.exec = lambda self: QDialog.DialogCode.Accepted
    panel.open_settings_dialog()
    panel.start_llm_in_background.assert_called_once_with()


def test_switching_back_to_local_loads_the_bundled_engine(panel, monkeypatch):
    from scripts.desktop_companion import QDialog
    panel.orchestrator.persona_manager.set_llm_provider("ollama")

    class FakeDialog:
        def __init__(self, pm, parent=None):
            self.pm = pm

        def exec(self):
            self.pm.set_llm_provider("local")
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr("scripts.desktop_companion.OrdisPersonaDialog", FakeDialog)
    monkeypatch.setattr(panel, "add_chat_bubble", lambda *a, **kw: None)
    panel.start_llm_in_background = MagicMock()
    panel.open_settings_dialog()
    panel.start_llm_in_background.assert_called_once_with(download_binaries=True)


def test_launcher_skips_model_download_for_hosted_engine(tmp_path, monkeypatch, capsys):
    from scripts import embedded_llm_runner as elr
    pm = PersonaManager()  # the test session's WF_USER_DATA_DIR
    previous = pm.get_llm_provider()
    pm.set_llm_provider("gemini")
    try:
        monkeypatch.setattr(sys, "argv", ["embedded_llm_runner.py", "--download-bin", "--download-model", "--skip-if-remote"])
        with patch.object(elr.EmbeddedLLMRunner, "ensure_binaries_exist") as bins, \
                patch.object(elr.EmbeddedLLMRunner, "ensure_model_exists") as model, \
                pytest.raises(SystemExit) as exit_info:
            elr.main()
        assert exit_info.value.code == 0
        bins.assert_not_called()
        model.assert_not_called()
        assert "gemini" in capsys.readouterr().out
    finally:
        pm.set_llm_provider(previous)
