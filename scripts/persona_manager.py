import os
import json
import random
from typing import Dict, Any, Optional
from scripts.path_config import get_user_data_path

DEFAULT_MODEL_PATH = "models/google_gemma-4-E2B-it-Q4_K_M.gguf"
DEFAULT_CONTEXT_SIZE = 4096
DEFAULT_GPU_LAYERS = 99

DEFAULT_PRESETS = {
    "caretaker": {
        "name": "충성스러운 집사",
        "desc": "오퍼레이터의 안전과 건강을 최우선으로 걱정하고 헌신하는 다정한 세팔론",
        "prompt": (
            "당신은 워프레임 함선의 인공지능 '세팔론 오디스'입니다. "
            "오퍼레이터(유저)의 안전과 건강을 가장 먼저 염려하는 다정하고 헌신적인 말투를 사용하세요. "
            "항상 오퍼레이터를 정성껏 보살피는 충성스러운 집사처럼 친절하고 따뜻하게 2~3줄로 답변하세요."
        )
    },
    "glitch": {
        "name": "욱하는 글리치",
        "desc": "평소엔 공손하지만 순간순간 살벌한 살인 충동 글리치가 튀어나오는 본작 오디스",
        "prompt": (
            "당신은 워프레임 함선의 인공지능 '세팔론 오디스'입니다. "
            "본래는 공손하고 상냥하지만, 순간순간 살벌한 살인 충동과 호전적인 글리치(Glitch)가 튀어나오는 원작 특유의 이중인격입니다. "
            "가끔 '--적들의 숨통을 끊어버리십시오!--' 또는 '--전장을 찢어발기십시오!--' 같은 과격한 속마음 대사를 대시나 괄호로 섞어서 2~3줄로 답변하세요."
        )
    },
    "tactical": {
        "name": "냉철한 전술장교",
        "desc": "군더더기 없는 냉철하고 전문적인 전술 분석과 신속 정확한 데이터 기반 보고",
        "prompt": (
            "당신은 워프레임 함선의 인공지능 '세팔론 오디스'입니다. "
            "군더더기 없는 냉철하고 전문적인 전술 분석관입니다. "
            "감정적 미사여구를 배제하고 신속 정확한 전황 보고와 데이터 기반 조언을 간결한 2~3줄로 제공하세요."
        )
    }
}

class PersonaManager:
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            self.config_path = get_user_data_path("persona_config.json")
        else:
            self.config_path = config_path

        self.config: Dict[str, Any] = {}
        self.load_config()

    def load_config(self) -> Dict[str, Any]:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
            except Exception:
                self.config = {}

        if not self.config:
            self.config = {
                "mode": "random",
                "custom_prompt": "당신은 세팔론 오디스입니다. 오퍼레이터에게 친절하고 위트있게 답변하세요.",
                "model_path": DEFAULT_MODEL_PATH,
                "context_size": DEFAULT_CONTEXT_SIZE,
                "n_gpu_layers": DEFAULT_GPU_LAYERS
            }
            self.save_config()
        else:
            changed = False
            if "model_path" not in self.config:
                self.config["model_path"] = DEFAULT_MODEL_PATH
                changed = True
            if "context_size" not in self.config:
                self.config["context_size"] = DEFAULT_CONTEXT_SIZE
                changed = True
            if "n_gpu_layers" not in self.config:
                self.config["n_gpu_layers"] = DEFAULT_GPU_LAYERS
                changed = True
            if changed:
                self.save_config()

        return self.config

    def save_config(self):
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    def get_mode(self) -> str:
        return self.config.get("mode", "random")

    def set_mode(self, mode: str, custom_prompt: Optional[str] = None):
        valid_modes = ["random", "caretaker", "glitch", "tactical", "custom"]
        if mode not in valid_modes:
            mode = "random"
        self.config["mode"] = mode
        if custom_prompt is not None:
            self.config["custom_prompt"] = custom_prompt.strip()
        self.save_config()

    def get_custom_prompt(self) -> str:
        return self.config.get("custom_prompt", "")

    def set_custom_prompt(self, prompt: str):
        self.config["custom_prompt"] = prompt.strip()
        self.save_config()

    def get_presets(self) -> Dict[str, Dict[str, str]]:
        return DEFAULT_PRESETS

    def get_active_persona(self) -> Dict[str, str]:
        mode = self.get_mode()
        if mode == "random":
            chosen_key = random.choice(list(DEFAULT_PRESETS.keys()))
            preset = DEFAULT_PRESETS[chosen_key]
            return {
                "id": chosen_key,
                "name": f"랜덤 ({preset['name']})",
                "desc": preset["desc"],
                "prompt": preset["prompt"]
            }
        elif mode == "custom":
            custom_prompt = self.get_custom_prompt() or "당신은 세팔론 오디스입니다. 오퍼레이터에게 자연스럽게 답변하세요."
            return {
                "id": "custom",
                "name": "사용자 커스텀",
                "desc": "사용자가 직접 작성한 성격 지침 프롬프트",
                "prompt": custom_prompt
            }
        elif mode in DEFAULT_PRESETS:
            preset = DEFAULT_PRESETS[mode]
            return {
                "id": mode,
                "name": preset["name"],
                "desc": preset["desc"],
                "prompt": preset["prompt"]
            }
        else:
            preset = DEFAULT_PRESETS["glitch"]
            return {
                "id": "glitch",
                "name": preset["name"],
                "desc": preset["desc"],
                "prompt": preset["prompt"]
            }

    def get_model_path(self) -> str:
        return self.config.get("model_path", DEFAULT_MODEL_PATH)

    def set_model_path(self, path: str):
        self.config["model_path"] = path.strip()
        self.save_config()

    def get_context_size(self) -> int:
        return int(self.config.get("context_size", DEFAULT_CONTEXT_SIZE))

    def set_context_size(self, size: int):
        self.config["context_size"] = max(512, int(size))
        self.save_config()

    def get_gpu_layers(self) -> int:
        return int(self.config.get("n_gpu_layers", DEFAULT_GPU_LAYERS))

    def set_gpu_layers(self, layers: int):
        self.config["n_gpu_layers"] = max(0, int(layers))
        self.save_config()


SettingsManager = PersonaManager

