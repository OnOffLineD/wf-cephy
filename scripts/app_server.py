import http.server
import socketserver
import json
import webbrowser
import os
import sys
import subprocess
import atexit
import time
import urllib.request
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from scripts.llm_orchestrator import LLMOrchestrator

PORT = 5000
orchestrator = None
llama_process = None

def start_llama_server():
    global llama_process
    bin_server = root_dir / "bin" / "llama-server.exe"
    model_path = root_dir / "models" / "gemma4-e4b.gguf"

    if bin_server.exists() and model_path.exists():
        # Check if already running on 8080
        try:
            with urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=1) as resp:
                if resp.status == 200:
                    print("[WF-Optimizer] Portable llama-server already active on port 8080.")
                    return
        except Exception:
            pass

        print(f"[WF-Optimizer] Initializing portable Gemma 4 E4B engine...")
        cmd = [
            str(bin_server),
            "-m", str(model_path),
            "--port", "8080",
            "-c", "4096",
            "--n-gpu-layers", "99",
            "--host", "127.0.0.1"
        ]
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        llama_process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags
        )
        print("[WF-Optimizer] Engine started. Waiting for model to load...")
        # Wait up to 30 seconds for server to be ready
        for _ in range(30):
            try:
                with urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=1) as resp:
                    if resp.status == 200:
                        print("[WF-Optimizer] [OK] Gemma 4 E4B engine is fully ready!")
                        return
            except Exception:
                time.sleep(1)
        print("[WF-Optimizer] Warning: Engine initialization timed out, continuing...")

def cleanup_llama_server():
    global llama_process
    if llama_process and llama_process.poll() is None:
        print("\n[WF-Optimizer] Cleaning up background engine...")
        llama_process.terminate()
        try:
            llama_process.wait(timeout=3)
        except Exception:
            llama_process.kill()

atexit.register(cleanup_llama_server)

class OptimizerHTTPHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(root_dir / "web"), **kwargs)

    def do_POST(self):
        if self.path == "/api/chat":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8')
            
            try:
                body = json.loads(post_data)
                query = body.get("query", "").strip()
                if not query:
                    raise ValueError("Query is empty")

                global orchestrator
                if orchestrator is None:
                    orchestrator = LLMOrchestrator(model="gemma4:e4b")

                result = orchestrator.chat(query)
                response_bytes = json.dumps(result, ensure_ascii=False).encode('utf-8')

                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(response_bytes)))
                self.end_headers()
                self.wfile.write(response_bytes)

            except Exception as e:
                err_bytes = json.dumps({"error": str(e)}, ensure_ascii=False).encode('utf-8')
                self.send_response(500)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(err_bytes)))
                self.end_headers()
                self.wfile.write(err_bytes)
        else:
            self.send_response(404)
            self.end_headers()

def run_server():
    # 1. Start portable LLM engine if present
    start_llama_server()

    # 2. Start Web server
    print(f"[WF-Optimizer] Starting web server at http://localhost:{PORT}")
    webbrowser.open(f"http://localhost:{PORT}")
    socketserver.TCPServer.allow_reuse_address = True
    try:
        with socketserver.TCPServer(("", PORT), OptimizerHTTPHandler) as httpd:
            print(f"[WF-Optimizer] Web UI ready. Press Ctrl+C to stop.")
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\n[WF-Optimizer] Server stopped by user.")
    except OSError as e:
        print(f"\n[WF-Optimizer ERROR] Port {PORT} is already in use or unavailable: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_server()
