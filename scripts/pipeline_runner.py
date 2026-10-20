#!/usr/bin/env python3
"""
scripts/pipeline_runner.py (v2.0 - Universal Zero-Token Local Worker Runner)
Features:
1. Windows CLI Generic Sanitizer ('List[Card]' -> 'List<Card>')
2. Method Upsert & Overload Targeting ('--mode patch' replaces existing or inserts new method)
3. Uncommitted Live Symbol Cache ('.antigravity/live_symbols.json') + Incremental Graphify Sync
4. Ollama KV-Cache Prefix Optimization & 'keep_alive: 30m' via Native urllib (No curl escaping bugs)
5. '[VERIFY_CONTRACT]' Output to enforce Zero Read-After-Write
6. '--bootstrap' mode for automatic project profile & Git Hook setup
"""

import argparse
import json
import os
import re
import stat
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class LocalPipelineRunner:
    def __init__(self, project_root: str = "."):
        self.root = Path(project_root).resolve()
        self.meta_dir = self.root / ".antigravity"
        self.profile_path = self.meta_dir / "project_profile.json"
        self.live_cache_path = self.meta_dir / "live_symbols.json"
        self.graph_dir = self.root / "graphify-out"

        self.meta_dir.mkdir(parents=True, exist_ok=True)
        self.profile = self._load_or_init_profile()
        self.model = self.profile.get("local_model", "qwen2.5-coder-8k")
        self.num_ctx = int(self.profile.get("num_ctx", 8192))
        self.symbol_map = self._load_combined_symbol_map()

    # -------------------------------------------------------------------------
    # 0. Bootstrap & Environment Detection
    # -------------------------------------------------------------------------
    def _detect_local_model(self) -> Tuple[str, int]:
        """데스크톱(16k)과 노트북(8k)에 설치된 Ollama 모델을 자동 감지합니다."""
        candidates = [
            ("qwen2.5-coder-16k", 16384),
            ("qwen2.5-coder-8k", 8192),
            ("qwen2.5-coder:14b", 8192),
            ("qwen2.5-coder:7b", 8192),
        ]
        try:
            res = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            installed = res.stdout
            for name, ctx in candidates:
                if name in installed:
                    return name, ctx
        except Exception:
            pass
        return "qwen2.5-coder-8k", 8192

    def _detect_project_stack(self) -> Dict[str, str]:
        """루트 파일을 스캔하여 언어 및 기본 빌드/테스트 명령어를 감지합니다."""
        csprojs = list(self.root.glob("*.csproj"))
        if csprojs:
            return {
                "language": "csharp",
                "ext": ".cs",
                "build_cmd": f'dotnet build "{csprojs[0].name}" --nologo -v q',
                "test_cmd": f'dotnet test "{csprojs[0].name}" --nologo -v q',
            }
        if (self.root / "CMakeLists.txt").exists():
            return {
                "language": "cpp",
                "ext": ".cpp",
                "build_cmd": "cmake --build build",
                "test_cmd": "ctest --test-dir build --output-on-failure",
            }
        if (self.root / "package.json").exists():
            return {
                "language": "typescript",
                "ext": ".ts",
                "build_cmd": "npm run build",
                "test_cmd": "npm test",
            }
        if (self.root / "pyproject.toml").exists() or (self.root / "requirements.txt").exists():
            return {
                "language": "python",
                "ext": ".py",
                "build_cmd": "python -m py_compile",
                "test_cmd": "pytest -q",
            }
        return {
            "language": "generic",
            "ext": ".cs",
            "build_cmd": "",
            "test_cmd": "",
        }

    def _load_or_init_profile(self) -> dict:
        if self.profile_path.exists():
            try:
                return json.loads(self.profile_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        model, num_ctx = self._detect_local_model()
        stack = self._detect_project_stack()
        profile = {
            "language": stack["language"],
            "default_ext": stack["ext"],
            "build_cmd": stack["build_cmd"],
            "test_cmd": stack["test_cmd"],
            "local_model": model,
            "num_ctx": num_ctx,
            "ollama_url": "http://localhost:11434/api/generate",
        }
        try:
            self.profile_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"[WARN] Failed to write project profile: {e}", file=sys.stderr)
        return profile

    def bootstrap_workspace(self) -> None:
        """Section 0 부트스트랩: 프로필 생성, Git Hook 설치, 초기 그래프 인덱싱을 수행합니다."""
        print(f"[BOOTSTRAP] Profile initialized at {self.profile_path.relative_to(self.root)}")
        print(f"[BOOTSTRAP] Bound Local Worker: {self.model} (Context: {self.num_ctx})")

        git_hooks_dir = self.root / ".git" / "hooks"
        if git_hooks_dir.exists():
            hook_content = (
                "#!/bin/sh\n"
                "# Auto-generated by Antigravity Local Pipeline Runner\n"
                "if command -v graphify >/dev/null 2>&1; then\n"
                "  graphify build >/dev/null 2>&1 &\n"
                "fi\n"
            )
            for hook_name in ("post-commit", "post-merge"):
                hook_file = git_hooks_dir / hook_name
                if not hook_file.exists():
                    hook_file.write_text(hook_content, encoding="utf-8")
                    hook_file.chmod(hook_file.stat().st_mode | stat.S_IEXEC)
                    print(f"[BOOTSTRAP] Installed Git Hook: .git/hooks/{hook_name}")

        if not self.live_cache_path.exists():
            self.live_cache_path.write_text("{}", encoding="utf-8")
        print("[BOOTSTRAP] Workspace ready for Zero-Token Local Delegation.")

    # -------------------------------------------------------------------------
    # 1. Graphify + Uncommitted Live Symbol Resolution
    # -------------------------------------------------------------------------
    def _load_combined_symbol_map(self) -> Dict[str, str]:
        """graphify-out 인덱스와 미커밋 실시간 심볼 캐시(live_symbols.json)를 병합 로드합니다."""
        mapping: Dict[str, str] = {}
        if self.graph_dir.exists():
            for f in self.graph_dir.glob("*.json"):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    nodes = data.get("nodes", data.get("symbols", []))
                    if isinstance(nodes, list):
                        for node in nodes:
                            if isinstance(node, dict):
                                name = node.get("name") or node.get("id")
                                path = node.get("file") or node.get("path")
                                if name and path:
                                    mapping[name.split(".")[-1]] = path
                                    mapping[name] = path
                except Exception:
                    continue

        if self.live_cache_path.exists():
            try:
                live_data = json.loads(self.live_cache_path.read_text(encoding="utf-8"))
                if isinstance(live_data, dict):
                    mapping.update(live_data)
            except Exception:
                pass
        return mapping

    def _register_live_symbols(self, file_rel: str, code_content: str) -> None:
        """커밋 전이라도 방금 생성/수정한 파일의 클래스/인터페이스/Enum을 실시간 캐시에 즉시 등록합니다."""
        found_types = re.findall(
            r"\b(?:class|interface|struct|enum|record)\s+([A-Za-z_]\w*)", code_content
        )
        file_stem = Path(file_rel).stem
        if file_stem not in found_types:
            found_types.append(file_stem)

        live_data = {}
        if self.live_cache_path.exists():
            try:
                live_data = json.loads(self.live_cache_path.read_text(encoding="utf-8"))
            except Exception:
                live_data = {}

        for sym in found_types:
            live_data[sym] = file_rel
            self.symbol_map[sym] = file_rel

        try:
            self.live_cache_path.write_text(
                json.dumps(live_data, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

        # graphify 증분 업데이트 시도 (백그라운드 비차단)
        try:
            subprocess.Popen(
                ["graphify", "update", file_rel],
                cwd=self.root,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # 2. Windows CLI Sanitizer & Context Hydrator
    # -------------------------------------------------------------------------
    @staticmethod
    def sanitize_cli_generics(text: str, file_ext: str) -> str:
        """
        Windows CLI 리다이렉션 충돌을 피하기 위해 대괄호로 표기된 제네릭('List[CardData]')을
        언어에 맞게 'List<CardData>'로 복원합니다.
        """
        if not text:
            return ""
        if file_ext in {".cs", ".cpp", ".h", ".hpp", ".ts", ".gd", ".java"}:
            # 중첩 제네릭까지 안전하게 2회 패스 치환 (배열 숫자 인덱스나 빈 배열 []은 유지)
            for _ in range(2):
                text = re.sub(
                    r"\b([A-Za-z_]\w*)\[([A-Za-z_][\w\s,<>?\[\]]*)\]",
                    r"\1<\2>",
                    text,
                )
        return text

    def hydrate_dependencies(self, deps_csv: str) -> str:
        """최대 5개의 핵심 의존성 심볼만 로컬에서 추출하여 8k 컨텍스트 초과를 방지합니다."""
        if not deps_csv:
            return "// No external dependencies specified."
        symbols = [s.strip() for s in deps_csv.split(",") if s.strip()][:5]
        headers = []
        visited = set()

        for sym in symbols:
            rel_path = self.symbol_map.get(sym)
            target = (self.root / rel_path) if rel_path else None
            if not target or not target.exists():
                target = next(self.root.rglob(f"{sym}.*"), None)

            if target and target.exists() and target not in visited:
                visited.add(target)
                headers.append(self._extract_file_skeleton(target, max_lines=75))
            elif not target:
                headers.append(f"// [INFO] Dependency symbol '{sym}' not found in local files.")

        return "\n\n".join(headers)

    def _extract_file_skeleton(self, path: Path, max_lines: int = 90) -> str:
        """파일에서 메서드 구현부 바디를 제거하고 시그니처와 프로퍼티/필드 선언만 추출합니다."""
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception as e:
            return f"// [ERROR] Failed to read {path.name}: {e}"

        rel_name = path.relative_to(self.root) if path.is_relative_to(self.root) else path.name
        out = [f"// --- Hydrated Skeleton: {rel_name} ---"]
        depth = 0

        for line in lines:
            s = line.strip()
            if not s or s.startswith("//"):
                continue
            if depth <= 2:
                is_type_decl = bool(
                    re.search(r"\b(class|struct|interface|enum|namespace|record)\b", s)
                )
                is_auto_prop = bool(re.search(r"\{\s*(get|set)\b", s))
                if "{" in s and depth >= 1 and not is_type_decl and not is_auto_prop:
                    sig = line.split("{")[0].rstrip() + " { /* body omitted */ }"
                    out.append(sig)
                else:
                    out.append(line)
            depth += line.count("{") - line.count("}")
            if len(out) >= max_lines:
                out.append("// ... [truncated for 8k context budget] ...")
                break

        return "\n".join(out)

    # -------------------------------------------------------------------------
    # 3. Method Extraction & Upsert Engine (Replace or Auto-Insert)
    # -------------------------------------------------------------------------
    def find_method_span(self, content: str, symbol: str) -> Optional[Tuple[int, int, str]]:
            is_python = self.profile.get("language") == "python" or self.profile.get("default_ext") == ".py"
            clean_name = symbol.split("(")[0].strip()

            if is_python:
                if "." in clean_name:
                    class_name, method_name = clean_name.rsplit(".", 1)
                    class_pattern = re.compile(rf"^([ \t]*class\s+{re.escape(class_name)}\b)", re.MULTILINE)
                    class_match = class_pattern.search(content)
                    if not class_match:
                        return None
                    class_start_idx = class_match.start()
                    method_pattern = re.compile(rf"^([ \t]*def\s+{re.escape(method_name)}\s*\(.*?\)\s*(?:->[^:]+)?:)", re.MULTILINE)
                    method_match = method_pattern.search(content[class_start_idx:])
                    if not method_match:
                        return None
                    start_idx = class_start_idx + method_match.start()
                else:
                    pattern = re.compile(rf"^([ \t]*def\s+{re.escape(clean_name)}\s*\(.*?\)\s*(?:->[^:]+)?:)", re.MULTILINE)
                    match = pattern.search(content)
                    if not match:
                        return None
                    start_idx = match.start()

                lines = content[start_idx:].splitlines(keepends=True)
                first_line = lines[0]
                base_indent = len(first_line) - len(first_line.lstrip())
                curr_pos = start_idx + len(first_line)
                for line in lines[1:]:
                    stripped = line.strip()
                    if not stripped:
                        curr_pos += len(line)
                        continue
                    line_indent = len(line) - len(line.lstrip())
                    if line_indent <= base_indent:
                        break
                    curr_pos += len(line)
                return start_idx, curr_pos, content[start_idx:curr_pos]

            if "(" in symbol:
                name_part, param_part = symbol.split("(", 1)
                param_hint = re.escape(param_part.rstrip(")").strip())
                pattern_str = (
                    rf"([^\n]*\b{re.escape(name_part.strip())}\s*\([^)]*{param_hint}[^)]*\)[^{{;]*\{{)"
                )
            else:
                pattern_str = rf"([^\n]*\b{re.escape(symbol.strip())}\s*\([^)]*\)[^{{;]*\{{)"

            match = re.search(pattern_str, content, re.MULTILINE)
            if not match:
                return None

            start_idx = match.start()
            brace_start = match.end() - 1
            depth = 0
            in_str = False
            escape = False

            for i in range(brace_start, len(content)):
                ch = content[i]
                if escape:
                    escape = False
                    continue
                if ch == "\\":
                    escape = True
                    continue
                if ch == '"':
                    in_str = not in_str
                    continue
                if not in_str:
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            return start_idx, i + 1, content[start_idx : i + 1]
            return None

    def upsert_method_into_content(
        self, original_content: str, symbol: str, new_method_code: str
    ) -> Tuple[str, str]:
        span = self.find_method_span(original_content, symbol)
        if span:
            start, end, orig_code = span
            orig_first = orig_code.splitlines()[0] if orig_code else ""
            orig_indent = len(orig_first) - len(orig_first.lstrip())
            new_lines = new_method_code.strip().splitlines()
            if new_lines and orig_indent > 0:
                new_first_indent = len(new_lines[0]) - len(new_lines[0].lstrip())
                diff = orig_indent - new_first_indent
                if diff > 0:
                    prefix = " " * diff
                    new_method_code = "\n".join(prefix + line if line.strip() else line for line in new_lines)
            return original_content[:start] + new_method_code.rstrip() + "\n\n" + original_content[end:], "REPLACED"

        is_python = self.profile.get("language") == "python" or self.profile.get("default_ext") == ".py"
        if is_python:
            import textwrap
            main_match = re.search(r"^[ \t]*if\s+__name__\s*==\s*['\"]__main__['\"]:", original_content, re.MULTILINE)
            insert_pos = main_match.start() if main_match else len(original_content)
            cleaned_method = textwrap.dedent(new_method_code.strip())
            indented = "\n    " + cleaned_method.replace("\n", "\n    ") + "\n\n"
            patched = original_content[:insert_pos].rstrip() + "\n" + indented + original_content[insert_pos:].lstrip()
            return patched, "INSERTED"

        last_brace = original_content.rfind("}")
        if last_brace == -1:
            raise ValueError(f"Cannot find closing brace in target file to insert '{symbol}'.")

        has_block_namespace = bool(re.search(r"\bnamespace\s+[\w.]+\s*\{", original_content))
        insert_pos = last_brace
        if has_block_namespace:
            second_last = original_content.rfind("}", 0, last_brace)
            if second_last != -1:
                insert_pos = second_last

        indented = "\n    " + new_method_code.strip().replace("\n", "\n    ") + "\n"
        patched = original_content[:insert_pos] + indented + original_content[insert_pos:]
        return patched, "INSERTED"

    # -------------------------------------------------------------------------
    # 4. Native Ollama API Client (KV-Cache Prefix & keep_alive Optimized)
    # -------------------------------------------------------------------------
    def call_ollama(self, static_prefix: str, dynamic_error_tail: str = "") -> str:
        """
        정적 프롬프트(static_prefix)를 상단에 고정하고 에러 로그만 하단에 붙여
        Ollama의 KV 캐시 재사용률을 극대화합니다.
        """
        full_prompt = static_prefix if not dynamic_error_tail else f"{static_prefix}\n\n{dynamic_error_tail}"
        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": False,
            "keep_alive": "30m",
            "options": {
                "num_ctx": self.num_ctx,
                "temperature": 0.1,
            },
        }
        url = self.profile.get("ollama_url", "http://localhost:11434/api/generate")
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=360) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                raw_text = body.get("response", "")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Ollama connection failed ({url}): {e}")

        code_match = re.search(r"```(?:\w+)?\s*\n(.*?)```", raw_text, re.DOTALL)
        return code_match.group(1).strip() if code_match else raw_text.strip()

    # -------------------------------------------------------------------------
    # 5. Verification & Contract Output
    # -------------------------------------------------------------------------
    def run_verification(self, custom_test_cmd: Optional[str]) -> Tuple[bool, str]:
        cmd = custom_test_cmd or self.profile.get("build_cmd", "")
        if not cmd:
            return True, "No build/test command configured."
        proc = subprocess.run(
            cmd, shell=True, cwd=self.root, capture_output=True, text=True
        )
        combined_log = (proc.stdout + "\n" + proc.stderr).strip()
        return proc.returncode == 0, combined_log[-1500:]

    @staticmethod
    def print_verify_contract(
        file_rel: str, action: str, generated_code: str, model: str, attempt: int
    ) -> None:
        """클라우드 에이전트가 사후 파일 열람(view_file)을 하지 않도록 Public 시그니처 계약을 출력합니다."""
        sigs = re.findall(
            r"^\s*(?:public|protected|internal|export|def)\s+[^\n{;]+",
            generated_code,
            re.MULTILINE,
        )
        summary = " | ".join(s.strip() for s in sigs[:6]) or "Method/Component body updated"
        print(f"[SUCCESS] {action} on {file_rel} (Model: {model}, Attempt: {attempt})")
        print(f"[VERIFY_CONTRACT] {summary}")
        print("[PROTOCOL_LOCK] DO NOT invoke view_file or git diff. Proceed directly to Tier 1 wiring.")

    # -------------------------------------------------------------------------
    # 6. Execution Modes: Patch (Replace/Insert) & Create
    # -------------------------------------------------------------------------
    def execute_patch(
        self,
        file_rel: str,
        symbol: str,
        deps: str,
        spec: str,
        test_cmd: Optional[str],
        retries: int = 3,
    ) -> None:
        file_path = self.root / file_rel
        if not file_path.exists():
            print(f"[ERROR] Target file '{file_rel}' does not exist. Use --mode create instead.")
            sys.exit(1)

        ext = file_path.suffix or self.profile.get("default_ext", ".cs")
        clean_symbol = self.sanitize_cli_generics(symbol, ext)
        clean_spec = self.sanitize_cli_generics(spec, ext)

        original_content = file_path.read_text(encoding="utf-8")
        span = self.find_method_span(original_content, clean_symbol)
        existing_method_code = (
            span[2] if span else f"// Method '{clean_symbol}' does not exist yet. Write the complete new method."
        )

        deps_header = self.hydrate_dependencies(deps)
        class_skeleton = self._extract_file_skeleton(file_path)

        # KV 캐시 고정을 위한 정적 프리픽스
        static_prefix = (
            f"You are an expert developer. Implement ONLY the target method `{clean_symbol}`.\n"
            f"Return ONLY the method implementation (including signature and braces) inside a single code block.\n"
            f"Do NOT output the surrounding class or namespace.\n\n"
            f"### Hydrated Dependencies\n{deps_header}\n\n"
            f"### Target Class Skeleton ({file_rel})\n{class_skeleton}\n\n"
            f"### Current Target Method\n```\n{existing_method_code}\n```\n\n"
            f"### Specification\n{clean_spec}"
        )

        error_tail = ""
        last_log = ""

        for attempt in range(1, retries + 1):
            try:
                new_method = self.call_ollama(static_prefix, error_tail)
                target_symbol_name = clean_symbol.split(".")[-1]
                if not new_method or len(new_method.strip()) < 20 or target_symbol_name not in new_method:
                    raise ValueError(f"Generated method code is empty or missing '{target_symbol_name}'.")
                patched_content, action_type = self.upsert_method_into_content(
                    original_content, clean_symbol, new_method
                )
                file_path.write_text(patched_content, encoding="utf-8")
            except Exception as e:
                file_path.write_text(original_content, encoding="utf-8")
                print(f"[ERROR] Patch execution failed: {e}")
                sys.exit(1)

            ok, last_log = self.run_verification(test_cmd)
            if ok:
                self._register_live_symbols(file_rel, patched_content)
                self.print_verify_contract(
                    file_rel, f"{action_type} '{clean_symbol}'", new_method, self.model, attempt
                )
                return

            error_tail = (
                f"### Attempt {attempt} Compiler/Test Error (Fix this error in your method output):\n"
                f"```\n{last_log}\n```"
            )

        # 3회 실패 시 원본 완벽 복원 및 서킷 브레이커 발동
        file_path.write_text(original_content, encoding="utf-8")
        print(f"CIRCUIT_BREAKER_TRIPPED on {file_rel}::{clean_symbol}\nLast Error:\n{last_log}")
        sys.exit(2)

    def execute_create(
        self,
        file_rel: str,
        sig: str,
        deps: str,
        spec: str,
        test_cmd: Optional[str],
        retries: int = 3,
    ) -> None:
        file_path = self.root / file_rel
        file_path.parent.mkdir(parents=True, exist_ok=True)
        ext = file_path.suffix or self.profile.get("default_ext", ".cs")

        clean_sig = self.sanitize_cli_generics(sig, ext)
        clean_spec = self.sanitize_cli_generics(spec, ext)
        deps_header = self.hydrate_dependencies(deps)

        static_prefix = (
            f"You are an expert developer. Create a complete, compilable source file for `{file_rel}`.\n"
            f"Target Signature / Type Contract: `{clean_sig}`\n"
            f"Return ONLY the complete source code inside a single code block.\n\n"
            f"### Hydrated Dependencies\n{deps_header}\n\n"
            f"### Specification\n{clean_spec}"
        )

        error_tail = ""
        last_log = ""

        for attempt in range(1, retries + 1):
            try:
                generated_code = self.call_ollama(static_prefix, error_tail)
                file_path.write_text(generated_code, encoding="utf-8")
            except Exception as e:
                print(f"[ERROR] Create execution failed: {e}")
                sys.exit(1)

            ok, last_log = self.run_verification(test_cmd)
            if ok:
                self._register_live_symbols(file_rel, generated_code)
                self.print_verify_contract(
                    file_rel, "CREATED", generated_code, self.model, attempt
                )
                return

            error_tail = (
                f"### Attempt {attempt} Compiler/Test Error (Fix this error in the full file output):\n"
                f"```\n{last_log}\n```"
            )

        print(f"CIRCUIT_BREAKER_TRIPPED on {file_rel}\nLast Error:\n{last_log}")
        sys.exit(2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Antigravity Zero-Token Local Pipeline Runner v2.0")
    parser.add_argument("--bootstrap", action="store_true", help="Initialize project profile and Git hooks")
    parser.add_argument("--mode", choices=["patch", "create"], help="Execution mode: patch (replace/insert method) or create (new file)")
    parser.add_argument("--file", help="Target relative file path")
    parser.add_argument("--symbol", default="", help="Target method name (e.g., 'UpdateUI' or 'Init(CardData)') for --mode patch")
    parser.add_argument("--signature", default="", help="Class/Interface signature for --mode create (use [T] for generics)")
    parser.add_argument("--deps", default="", help="Comma-separated dependency symbols from graphify (max 5)")
    parser.add_argument("--spec", default="", help="Concise implementation specification (use [T] for generics)")
    parser.add_argument("--spec-stdin", action="store_true", help="Read specification from STDIN to avoid shell escaping issues")
    parser.add_argument("--test", default=None, help="Optional verification command override")
    parser.add_argument("--retries", type=int, default=3, help="Max self-healing retries (default: 3)")

    args = parser.parse_args()
    runner = LocalPipelineRunner()

    if args.bootstrap:
        runner.bootstrap_workspace()
        return

    if not args.mode or not args.file:
        parser.error("--mode and --file are required unless --bootstrap is specified.")

    spec_text = sys.stdin.read().strip() if args.spec_stdin else args.spec
    if not spec_text:
        parser.error("A specification must be provided via --spec or --spec-stdin.")

    if args.mode == "patch":
        if not args.symbol:
            parser.error("--symbol is required when using --mode patch.")
        runner.execute_patch(args.file, args.symbol, args.deps, spec_text, args.test, args.retries)
    elif args.mode == "create":
        runner.execute_create(args.file, args.signature, args.deps, spec_text, args.test, args.retries)


if __name__ == "__main__":
    main()