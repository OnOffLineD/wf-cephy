"""Chat backends for Ordis: the bundled llama.cpp server, Ollama, and hosted APIs (OpenAI, Claude, Gemini, ...).

Only the bundled server understands GBNF grammars. The others get the same prompts without one, so their
answers go through the same checks the callers already make (exact labels, tool JSON, invented numbers).
"""
import base64
import ctypes
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

import requests

from scripts.path_config import get_user_data_path, write_json_atomic

LOCAL_PROVIDER = "local"
OLLAMA_DEFAULT_URL = "http://localhost:11434"
ANTHROPIC_VERSION = "2023-06-01"
# Claude requires a cap; Ordis answers in 2~5 sentences, so this is never the limit in practice.
ANTHROPIC_MAX_TOKENS = 1024
# Hosted and Ollama replies can be slower than the warm local server (cold model load, reasoning models).
REMOTE_MIN_TIMEOUT = 30
REMOTE_TIMEOUT_SCALE = 2

PROVIDERS: Dict[str, Dict[str, Any]] = {
    "local": {
        "label": "내장 로컬 엔진 (llama.cpp)", "protocol": "llamacpp",
        "base_url": "http://127.0.0.1:18080", "model": "", "needs_key": False, "key_env": (), "models": (),
    },
    "ollama": {
        # Usually a remote Ollama behind an auth proxy, or ollama.com: the key goes out as "Authorization: Bearer".
        # Optional, so an open server on the LAN or this PC still works with the field left empty.
        "label": "Ollama (API 서버)", "protocol": "ollama",
        "base_url": OLLAMA_DEFAULT_URL, "model": "gemma3:4b", "needs_key": False, "key_env": ("OLLAMA_API_KEY",),
        "models": ("gemma3:4b", "gemma3:12b", "exaone3.5:7.8b", "qwen3:8b"),
    },
    "openai": {
        "label": "OpenAI (ChatGPT)", "protocol": "openai",
        "base_url": "https://api.openai.com/v1", "model": "gpt-5-mini", "needs_key": True,
        "key_env": ("OPENAI_API_KEY",), "models": ("gpt-5-mini", "gpt-5-nano", "gpt-4.1-mini", "gpt-4o-mini"),
    },
    "anthropic": {
        "label": "Anthropic Claude", "protocol": "anthropic",
        "base_url": "https://api.anthropic.com", "model": "claude-haiku-5-5", "needs_key": True,
        "key_env": ("ANTHROPIC_API_KEY",), "models": ("claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5"),
    },
    "gemini": {
        # Google's OpenAI-compatible endpoint, so it shares the OpenAI wire format.
        "label": "Google Gemini", "protocol": "openai",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "model": "gemini-2.5-flash",
        "needs_key": True, "key_env": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        "models": ("gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro"),
    },
    "openai_compat": {
        "label": "OpenAI 호환 (OpenRouter·Groq·DeepSeek·LM Studio 등)", "protocol": "openai",
        "base_url": "", "model": "", "needs_key": False, "key_env": ("WF_LLM_API_KEY",), "models": (),
    },
}

THINK_BLOCK = re.compile(r"<think>.*?(</think>|$)", re.S | re.I)
CODE_FENCE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")


def provider_ids() -> List[str]:
    return list(PROVIDERS)


def normalize_provider(provider: Optional[str]) -> str:
    return provider if provider in PROVIDERS else LOCAL_PROVIDER


def _ollama_host_url() -> str:
    """OLLAMA_HOST as Ollama itself reads it ("0.0.0.0", "host:port" or a full URL), turned into a URL to call."""
    host = (os.environ.get("OLLAMA_HOST") or "").strip()
    if not host:
        return OLLAMA_DEFAULT_URL
    if "://" not in host:
        host = f"http://{host}"
    scheme, rest = host.split("://", 1)
    hostport = rest.split("/", 1)[0]
    # A server bound to every interface is reached on loopback; Windows refuses to connect to 0.0.0.0.
    hostport = hostport.replace("0.0.0.0", "127.0.0.1")
    if ":" not in hostport.rsplit("]", 1)[-1]:
        hostport += ":11434"
    return f"{scheme}://{hostport}"


def default_base_url(provider: str) -> str:
    provider = normalize_provider(provider)
    if provider == "ollama":
        return _ollama_host_url()
    return PROVIDERS[provider]["base_url"]


def clean_reply(text: Optional[str]) -> str:
    """Drops a reasoning model's <think> block, which is not part of the answer."""
    return THINK_BLOCK.sub("", text or "").strip()


def extract_json_object(text: Optional[str]) -> Optional[Dict[str, Any]]:
    """The first JSON object in a reply, also when a hosted model wraps it in a code fence or a sentence."""
    if not text:
        return None
    body = CODE_FENCE.sub("", text.strip())
    candidates = [body]
    start, end = body.find("{"), body.rfind("}")
    if 0 <= start < end:
        candidates.append(body[start:end + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def tool_call_schema(tools: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """JSON schema for Ollama's `format`, the counterpart of build_gbnf_tool_grammar for that backend.

    Flat on purpose (no anyOf): the caller still checks that the args match the chosen tool.
    """
    arg_names: List[str] = []
    for meta in tools.values():
        for arg in meta.get("args") or ["task"]:
            if arg not in arg_names:
                arg_names.append(arg)
    arg_sets = {tuple(meta.get("args") or ["task"]) for meta in tools.values()}
    args_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {name: {"type": "string"} for name in arg_names},
    }
    if len(arg_sets) == 1:
        args_schema["required"] = list(next(iter(arg_sets)))
    return {
        "type": "object",
        "properties": {"tool": {"type": "string", "enum": list(tools)}, "args": args_schema},
        "required": ["tool", "args"],
    }


def label_schema(labels) -> Dict[str, Any]:
    return {"type": "object", "properties": {"label": {"type": "string", "enum": list(labels)}}, "required": ["label"]}


def _error_text(response: Any) -> str:
    """The provider's own error message: OpenAI/Claude nest it, Ollama gives a string, Gemini may wrap it in a list."""
    try:
        data = response.json()
    except ValueError:
        return (getattr(response, "text", "") or "").strip()[:200]
    if isinstance(data, list) and data:
        data = data[0]
    if isinstance(data, dict):
        err = data.get("error", data)
        if isinstance(err, dict):
            return str(err.get("message") or err.get("type") or err)[:200]
        return str(err)[:200]
    return str(data)[:200]


def describe_http_error(status: int, detail: str) -> str:
    hints = {
        401: "API 키가 거부되었습니다. 키를 다시 확인해 주십시오.",
        403: "이 키로는 해당 모델/기능을 쓸 권한이 없습니다.",
        404: "모델 이름이나 API 주소를 찾을 수 없습니다.",
        429: "요청 한도나 크레딧이 소진되었습니다. 잠시 후 다시 시도하거나 결제 상태를 확인해 주십시오.",
    }
    hint = hints.get(status) or ("서버 쪽 오류입니다. 잠시 후 다시 시도해 주십시오." if status >= 500 else "요청이 거부되었습니다.")
    return f"HTTP {status}: {hint}" + (f" ({detail})" if detail else "")


class LLMClient:
    """One configured backend. complete() returns the reply text, or None with the reason in last_error."""

    def __init__(self, provider: str = LOCAL_PROVIDER, base_url: str = "", model: str = "",
                 api_key: str = "", context_size: int = 4096):
        self.provider = normalize_provider(provider)
        preset = PROVIDERS[self.provider]
        self.protocol = preset["protocol"]
        self.base_url = (base_url or default_base_url(self.provider)).strip().rstrip("/")
        self.model = (model or preset["model"]).strip()
        self.api_key = (api_key or "").strip()
        self.context_size = context_size
        self.last_error = ""

    @property
    def is_local(self) -> bool:
        return self.protocol == "llamacpp"

    @property
    def supports_grammar(self) -> bool:
        return self.protocol == "llamacpp"

    @property
    def label(self) -> str:
        name = PROVIDERS[self.provider]["label"]
        return f"{name} · {self.model}" if self.model and not self.is_local else name

    def missing_setting(self) -> Optional[str]:
        """Why this backend can't be called yet, or None."""
        if self.is_local:
            return None
        if not self.base_url:
            return "API 주소(Base URL)가 비어 있습니다."
        if not self.model:
            return "모델 이름이 비어 있습니다."
        if PROVIDERS[self.provider]["needs_key"] and not self.api_key:
            return "API 키가 없습니다. 설정 > AI 엔진에서 키를 입력해 주십시오."
        return None

    # ----------------------------------------------------------------- requests
    def _headers(self) -> Dict[str, str]:
        if self.protocol == "anthropic":
            return {"x-api-key": self.api_key, "anthropic-version": ANTHROPIC_VERSION}
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

    def _anthropic_root(self) -> str:
        # Accept both "https://api.anthropic.com" and ".../v1".
        return self.base_url[:-3] if self.base_url.endswith("/v1") else self.base_url

    def _post(self, url: str, payload: Dict[str, Any], timeout: float, retry_without=()) -> Optional[Any]:
        response = requests.post(url, json=payload, headers=self._headers(), timeout=timeout)
        if response.status_code == 400 and any(k in payload for k in retry_without):
            # Reasoning models (o-series, gpt-5) reject a custom temperature; the default still answers.
            response = requests.post(url, json={k: v for k, v in payload.items() if k not in retry_without},
                                     headers=self._headers(), timeout=timeout)
        if response.status_code != 200:
            self.last_error = describe_http_error(response.status_code, _error_text(response))
            return None
        return response.json()

    def complete(self, system: str, user: str, temperature: float = 0.5, grammar: Optional[str] = None,
                 json_schema: Optional[Dict[str, Any]] = None, max_tokens: Optional[int] = None,
                 timeout: float = 35, url: Optional[str] = None) -> Optional[str]:
        """One system + user turn. `grammar` only reaches llama.cpp and `json_schema` only Ollama.

        `max_tokens` is local-only too: a hosted reasoning model spends its cap on thinking and returns nothing.
        """
        self.last_error = ""
        problem = self.missing_setting()
        if problem:
            self.last_error = problem
            return None
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        if not self.is_local:
            timeout = max(REMOTE_MIN_TIMEOUT, timeout * REMOTE_TIMEOUT_SCALE)
        try:
            if self.protocol == "llamacpp":
                payload: Dict[str, Any] = {"messages": messages, "temperature": temperature, "stream": False}
                if grammar:
                    payload["grammar"] = grammar
                if max_tokens:
                    payload["max_tokens"] = max_tokens
                res = requests.post(url or f"{self.base_url}/v1/chat/completions", json=payload, timeout=timeout)
                if res.status_code != 200:
                    self.last_error = f"llama-server HTTP {res.status_code}"
                    return None
                choices = res.json().get("choices", [])
                return clean_reply(choices[0].get("message", {}).get("content", "")) if choices else None

            if self.protocol == "ollama":
                payload = {"model": self.model, "messages": messages, "stream": False,
                           "options": {"temperature": temperature, "num_ctx": int(self.context_size)}}
                if json_schema:
                    payload["format"] = json_schema
                data = self._post(f"{self.base_url}/api/chat", payload, timeout)
                return clean_reply((data.get("message") or {}).get("content")) if data else None

            if self.protocol == "anthropic":
                payload = {"model": self.model, "max_tokens": ANTHROPIC_MAX_TOKENS, "system": system,
                           "messages": [{"role": "user", "content": user}], "temperature": temperature}
                data = self._post(f"{self._anthropic_root()}/v1/messages", payload, timeout, retry_without=("temperature",))
                if not data:
                    return None
                return clean_reply("".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"))

            payload = {"model": self.model, "messages": messages, "temperature": temperature, "stream": False}
            data = self._post(f"{self.base_url}/chat/completions", payload, timeout, retry_without=("temperature",))
            choices = (data or {}).get("choices") or []
            return clean_reply((choices[0].get("message") or {}).get("content")) if choices else None
        except requests.Timeout:
            self.last_error = f"응답 시간({int(timeout)}초)이 초과되었습니다."
        except requests.ConnectionError:
            self.last_error = f"{self.base_url} 에 연결할 수 없습니다."
        except Exception as e:  # A malformed reply must not crash the chat thread.
            self.last_error = f"응답을 읽지 못했습니다: {e}"
        return None

    # ----------------------------------------------------------------- checks
    def list_models(self, timeout: float = 10) -> Optional[List[str]]:
        """Model ids the backend offers. A free call, so it also checks the address and the key without spending tokens."""
        self.last_error = ""
        try:
            if self.protocol == "ollama":
                url = f"{self.base_url}/api/tags"
            elif self.protocol == "anthropic":
                url = f"{self._anthropic_root()}/v1/models"
            elif self.protocol == "openai":
                url = f"{self.base_url}/models"
            else:
                url = f"{self.base_url}/health"
            res = requests.get(url, headers=self._headers(), timeout=timeout)
            if res.status_code != 200:
                self.last_error = describe_http_error(res.status_code, _error_text(res))
                return None
            if self.is_local:
                return []
            data = res.json()
        except requests.RequestException:
            self.last_error = f"{self.base_url} 에 연결할 수 없습니다."
            return None
        except ValueError:
            self.last_error = "모델 목록 응답을 읽지 못했습니다."
            return None
        entries = data.get("models" if self.protocol == "ollama" else "data", []) if isinstance(data, dict) else []
        names = []
        for entry in entries:
            name = (entry.get("name") or entry.get("model")) if self.protocol == "ollama" else entry.get("id")
            if name:
                # Gemini lists "models/gemini-2.5-flash" but is called with the bare id.
                names.append(name[len("models/"):] if name.startswith("models/") else name)
        return names

    def has_model(self, names: List[str]) -> bool:
        return self.model in names or (self.protocol == "ollama" and f"{self.model}:latest" in names)

    def check_ready(self) -> Tuple[bool, str]:
        """Address, key and model checked without a paid request; the startup notice uses this.

        The message is the reason on failure, a warning on a doubtful success, and empty when all is well.
        """
        problem = self.missing_setting()
        if problem:
            return False, problem
        names = self.list_models()
        if names is None:
            # An HTTP answer (401 from the server's auth, ...) says more than "unreachable".
            if self.protocol == "ollama" and not self.last_error.startswith("HTTP"):
                return False, f"Ollama 서버({self.base_url})에 연결할 수 없습니다. 주소와 서버 실행 상태를 확인해 주십시오."
            return False, self.last_error
        if self.protocol == "ollama" and not self.has_model(names):
            installed = ", ".join(names[:5]) or "없음"
            return False, f"'{self.model}' 모델이 Ollama 서버에 없습니다. 서버에서 `ollama pull {self.model}`로 받아 두거나 목록의 모델을 고르십시오. (설치됨: {installed})"
        if names and not self.has_model(names):
            return True, f"연결은 되지만 '{self.model}' 이름이 모델 목록에 없습니다. 오타가 없는지 확인해 주십시오."
        return True, ""

    def test_connection(self) -> Tuple[bool, str]:
        """check_ready plus one tiny reply, so a wrong model name shows up before the first chat."""
        ok, message = self.check_ready()
        if not ok:
            return False, message
        reply = self.complete("Reply with the single word OK.", "ping", temperature=0.0, max_tokens=8, timeout=15)
        if reply is None:
            return False, self.last_error or "응답이 비어 있습니다."
        note = f"\n{message}" if message else ""
        return True, f"응답 확인: \"{reply[:40]}\"{note}"


# --------------------------------------------------------------------- keys
CRYPTPROTECT_UI_FORBIDDEN = 0x1
DPAPI_PREFIX = "dpapi:"
PLAIN_PREFIX = "plain:"


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _dpapi(data: bytes, protect: bool) -> bytes:
    """Windows DPAPI: only this Windows account on this PC can decrypt, so a synced copy of data/ is useless elsewhere."""
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    func = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    func.argtypes = [ctypes.POINTER(_DataBlob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                     ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(_DataBlob)]
    func.restype = ctypes.c_int
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    buffer = ctypes.create_string_buffer(data, len(data))
    blob_in = _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    blob_out = _DataBlob()
    if not func(ctypes.byref(blob_in), None, None, None, None, CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(blob_out)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        kernel32.LocalFree(ctypes.cast(blob_out.pbData, ctypes.c_void_p))


def _seal(secret: str) -> str:
    raw = secret.encode("utf-8")
    if sys.platform == "win32":
        try:
            return DPAPI_PREFIX + base64.b64encode(_dpapi(raw, protect=True)).decode("ascii")
        except OSError:
            pass
    return PLAIN_PREFIX + base64.b64encode(raw).decode("ascii")


def _unseal(stored: str) -> str:
    try:
        if stored.startswith(DPAPI_PREFIX) and sys.platform == "win32":
            return _dpapi(base64.b64decode(stored[len(DPAPI_PREFIX):]), protect=False).decode("utf-8")
        if stored.startswith(PLAIN_PREFIX):
            return base64.b64decode(stored[len(PLAIN_PREFIX):]).decode("utf-8")
    except (OSError, ValueError):
        pass
    # Sealed on another PC or account: treated as no key, and the user enters it again.
    return ""


class ApiKeyStore:
    """API keys, kept apart from persona_config.json (which git tracks) in data/api_keys.json (which it ignores)."""

    def __init__(self, path: Optional[str] = None):
        self.path = path or get_user_data_path("api_keys.json")

    def _load(self) -> Dict[str, str]:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return {}
        return {k: v for k, v in data.items() if isinstance(v, str)} if isinstance(data, dict) else {}

    def saved(self, provider: str) -> str:
        stored = self._load().get(provider)
        return _unseal(stored) if stored else ""

    def env_name(self, provider: str) -> Optional[str]:
        """The environment variable that supplies this provider's key, when one is set."""
        for name in PROVIDERS.get(provider, {}).get("key_env", ()):
            if os.environ.get(name, "").strip():
                return name
        return None

    def get(self, provider: str) -> str:
        """The saved key, else the provider's usual environment variable (OPENAI_API_KEY, ...)."""
        key = self.saved(provider)
        if key:
            return key
        env = self.env_name(provider)
        return os.environ[env].strip() if env else ""

    def set(self, provider: str, key: str) -> None:
        data = self._load()
        key = (key or "").strip()
        if key:
            data[provider] = _seal(key)
        elif provider in data:
            del data[provider]
        else:
            return
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        write_json_atomic(self.path, data)
