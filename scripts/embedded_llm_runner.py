import os
import sys
import subprocess
import time
import atexit
import requests
import ctypes
from ctypes import wintypes
from typing import Optional

class EmbeddedLLMRunner:
    def __init__(self, model_path='models/google_gemma-4-E2B-it-Q4_K_M.gguf', port=18080, host='127.0.0.1', n_gpu_layers=99, context_size=4096):
            root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            self.model_path = model_path if os.path.isabs(model_path) else os.path.join(root_dir, model_path)
            self.bin_path = os.path.join(root_dir, 'bin', 'llama-server.exe')
            self.port = port
            self.host = host
            self.n_gpu_layers = n_gpu_layers
            self.context_size = context_size
            self.process = None
            self.job_object = None
            self._is_starting = False
            if not getattr(EmbeddedLLMRunner, '_atexit_registered', False):
                atexit.register(self.stop_server)
                EmbeddedLLMRunner._atexit_registered = True

    def cleanup_existing_server(self):
        try:
            subprocess.run(
                ['taskkill', '/F', '/IM', 'llama-server.exe'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags= getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000),
                check=False
            )
        except Exception:
            pass

    def _assign_job_object(self, proc):
        kernel32 = ctypes.windll.kernel32
        job_name = "LLMJob"
        job_object = kernel32.CreateJobObjectW(None, job_name)
        if job_object == 0:
            raise ctypes.WinError(ctypes.get_last_error())

        info = ctypes.c_size_t(ctypes.sizeof(ctypes.c_int))
        limit_info = ctypes.c_int(0x2000)  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        kernel32.SetInformationJobObject(job_object, 4, ctypes.byref(limit_info), info)

        kernel32.AssignProcessToJobObject(job_object, proc._handle)
        self.job_object = job_object

    def start_server(self, wait_ready=True, timeout=90) -> bool:
                if self.is_healthy():
                    return True
                if getattr(self, '_is_starting', False):
                    if wait_ready:
                        start_t = time.time()
                        while time.time() - start_t < timeout:
                            if self.is_healthy():
                                return True
                            time.sleep(1)
                        return False
                    else:
                        return True
                self._is_starting = True
                self.cleanup_existing_server()
                if not self.ensure_binaries_exist():
                    self._is_starting = False
                    return False
                if not os.path.exists(self.bin_path):
                    self._is_starting = False
                    return False
                if not self.ensure_model_exists():
                    self._is_starting = False
                    return False
                if not os.path.exists(self.model_path):
                    self._is_starting = False
                    return False
                args = [
                    self.bin_path,
                    '-m', self.model_path,
                    '--port', str(self.port),
                    '-ngl', str(self.n_gpu_layers),
                    '-c', str(self.context_size)
                ]
                flags = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)
                self.process = subprocess.Popen(
                    args,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=flags
                )
                self._assign_job_object(self.process)
                if wait_ready:
                    start_t = time.time()
                    while time.time() - start_t < timeout:
                        if self.is_healthy():
                            self._is_starting = False
                            return True
                        time.sleep(1)
                    self._is_starting = False
                    return False
                self._is_starting = False
                return True

    def stop_server(self):
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except Exception:
                pass
            self.process = None
        if self.job_object:
            try:
                ctypes.windll.kernel32.CloseHandle(self.job_object)
            except Exception:
                pass
            self.job_object = None
        self.cleanup_existing_server()

    def is_healthy(self) -> bool:
        try:
            response = requests.get(f'http://{self.host}:{self.port}/health')
            return response.status_code == 200
        except requests.RequestException:
            return False

# Example usage:
# runner = EmbeddedLLMRunner()
# runner.start_server()
# print(runner.is_healthy())
# runner.stop_server()

    def ensure_model_exists(self, progress_callback=None) -> bool:
            if os.path.exists(self.model_path) and os.path.getsize(self.model_path) > 1000000000:
                return True

            os.makedirs(os.path.dirname(self.model_path) or 'models', exist_ok=True)
            url = 'https://huggingface.co/bartowski/google_gemma-4-E2B-it-GGUF/resolve/main/google_gemma-4-E2B-it-Q4_K_M.gguf'
            tmp_path = self.model_path + '.download.tmp'

            try:
                response = requests.get(url, stream=True, timeout=30)
                response.raise_for_status()
                total_length = int(response.headers.get('content-length', 0))
                downloaded = 0

                with open(tmp_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if progress_callback:
                                percent = (downloaded / total_length) * 100 if total_length else 0
                                progress_callback(percent)

                os.rename(tmp_path, self.model_path)
                return True
            except Exception:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
                return False

    def ensure_binaries_exist(self) -> bool:
        if os.path.exists(self.bin_path):
            return True
        bin_dir = os.path.dirname(self.bin_path)
        if not os.path.exists(bin_dir):
            os.makedirs(bin_dir, exist_ok=True)
        return False

    def restart_server(self, context_size: Optional[int] = None) -> bool:
        if context_size is not None:
            self.context_size = context_size
        self.stop_server()
        self.cleanup_existing_server()
        return self.start_server(wait_ready=True)

    def main():
        import sys
    
        if '--start' in sys.argv:
            runner = EmbeddedLLMRunner()
            runner.ensure_model_exists()
            print('Started:', runner.start_server(wait_ready=True))
        elif '--stop' in sys.argv:
            runner = EmbeddedLLMRunner()
            runner.stop_server()
            print('Stopped')
        elif '--restart' in sys.argv:
            runner = EmbeddedLLMRunner()
            print('Restarted:', runner.restart_server())
        elif '--status' in sys.argv:
            runner = EmbeddedLLMRunner()
            print('Healthy:', runner.is_healthy())
        else:
            print('Usage: python embedded_llm_runner.py [--start|--stop|--restart|--status]')

if __name__ == '__main__':
    EmbeddedLLMRunner.main()

