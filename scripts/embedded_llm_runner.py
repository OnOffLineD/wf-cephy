import atexit
import ctypes
import os
import subprocess
import sys
import threading
import time
from ctypes import wintypes
from typing import Optional

import requests

from scripts.path_config import get_path, get_user_data_path

MODEL_URL = 'https://huggingface.co/bartowski/google_gemma-4-E2B-it-GGUF/resolve/main/google_gemma-4-E2B-it-Q4_K_M.gguf'
MIN_MODEL_BYTES = 1000000000
# Measured 31~114s from a synced Google Drive folder.
STARTUP_TIMEOUT_SECONDS = 300
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000


class _IoCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]


class _BasicLimitInformation(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _ExtendedLimitInformation(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _BasicLimitInformation),
        ("IoInfo", _IoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


def _kernel32():
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    kernel32.SetInformationJobObject.restype = wintypes.BOOL
    kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    return kernel32


def assign_kill_on_close_job(process: subprocess.Popen) -> Optional[int]:
    """Tie a child to a job so Windows ends it when this app dies, even on a crash or forced kill."""
    if sys.platform != "win32":
        return None
    kernel32 = _kernel32()
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    info = _ExtendedLimitInformation()
    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not kernel32.SetInformationJobObject(job, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION, ctypes.byref(info), ctypes.sizeof(info)):
        error = ctypes.get_last_error()
        kernel32.CloseHandle(job)
        raise ctypes.WinError(error)
    if not kernel32.AssignProcessToJobObject(job, int(process._handle)):
        error = ctypes.get_last_error()
        kernel32.CloseHandle(job)
        raise ctypes.WinError(error)
    return job


def close_job(job: Optional[int]) -> None:
    if job and sys.platform == "win32":
        _kernel32().CloseHandle(job)


class EmbeddedLLMRunner:
    def __init__(self, model_path='models/google_gemma-4-E2B-it-Q4_K_M.gguf', port=18080, host='127.0.0.1', n_gpu_layers=99, context_size=4096):
        self.model_path = model_path if os.path.isabs(model_path) else get_path(model_path)
        self.bin_path = get_path('bin', 'llama-server.exe')
        self.log_path = get_user_data_path('logs', 'llama-server.log')
        self.port = port
        self.host = host
        self.n_gpu_layers = n_gpu_layers
        self.context_size = context_size
        self.process = None
        self.job_object = None
        self.last_error = ""
        self._log_file = None
        self._start_lock = threading.Lock()
        atexit.register(self.stop_server)

    def _launch(self) -> bool:
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        self._log_file = open(self.log_path, "w", encoding="utf-8", errors="replace")
        args = [
            self.bin_path,
            '-m', self.model_path,
            '--host', self.host,
            '--port', str(self.port),
            '-ngl', str(self.n_gpu_layers),
            '-c', str(self.context_size)
        ]
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)
        try:
            self.process = subprocess.Popen(args, stdout=self._log_file, stderr=subprocess.STDOUT, creationflags=flags)
        except OSError as e:
            self.last_error = f"llama-server 실행 실패: {e}"
            self._close_log()
            return False
        try:
            self.job_object = assign_kill_on_close_job(self.process)
        except OSError:
            # The server still works; only crash cleanup is lost, and stop_server covers a normal exit.
            self.job_object = None
        return True

    def start_server(self, wait_ready=True, timeout=STARTUP_TIMEOUT_SECONDS) -> bool:
        if self.is_healthy():
            return True
        with self._start_lock:
            already_running = self.process is not None and self.process.poll() is None
            if not already_running:
                self.last_error = ""
                if not self.ensure_binaries_exist() or not self.ensure_model_exists():
                    return False
                if not self._launch():
                    return False
        return self.wait_for_ready(timeout=timeout) if wait_ready else True

    def stop_server(self):
        # Only this app's own process: other llama-server instances on the machine are not ours to kill.
        process, self.process = self.process, None
        if process is not None and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                process.kill()
        job, self.job_object = self.job_object, None
        close_job(job)
        self._close_log()

    def _close_log(self):
        log_file, self._log_file = self._log_file, None
        if log_file is not None:
            log_file.close()

    def is_healthy(self) -> bool:
        try:
            response = requests.get(f'http://{self.host}:{self.port}/health', timeout=1.5)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def is_ready(self) -> bool:
        return self.is_healthy()

    def wait_for_ready(self, timeout=10) -> bool:
        start_t = time.time()
        while time.time() - start_t < timeout:
            if self.is_healthy():
                return True
            if self.process is not None and self.process.poll() is not None:
                self.last_error = f"llama-server가 종료되었습니다 (코드 {self.process.returncode}). 로그: {self.log_path}"
                return False
            time.sleep(0.5)
        if not self.last_error and self.process is not None:
            self.last_error = f"llama-server가 {timeout}초 안에 준비되지 않았습니다. 로그: {self.log_path}"
        return False

    def ensure_model_exists(self, progress_callback=None) -> bool:
        if os.path.exists(self.model_path) and os.path.getsize(self.model_path) > MIN_MODEL_BYTES:
            return True

        os.makedirs(os.path.dirname(self.model_path) or 'models', exist_ok=True)
        tmp_path = self.model_path + '.download.tmp'
        try:
            response = requests.get(MODEL_URL, stream=True, timeout=30)
            response.raise_for_status()
            total_length = int(response.headers.get('content-length', 0))
            downloaded = 0
            with open(tmp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            progress_callback((downloaded / total_length) * 100 if total_length else 0)
            os.replace(tmp_path, self.model_path)
            return True
        except (requests.RequestException, OSError) as e:
            self.last_error = f"LLM 모델 다운로드 실패: {e}"
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            return False

    def ensure_binaries_exist(self) -> bool:
        if os.path.exists(self.bin_path):
            return True
        self.last_error = f"llama-server 실행 파일이 없습니다: {self.bin_path}"
        return False

    def restart_server(self, context_size: Optional[int] = None) -> bool:
        if context_size is not None:
            self.context_size = context_size
        self.stop_server()
        return self.start_server(wait_ready=True)


def main():
    runner = EmbeddedLLMRunner()
    if '--start' in sys.argv:
        print('Started:', runner.start_server(wait_ready=True))
    elif '--stop' in sys.argv:
        runner.stop_server()
        print('Stopped')
    elif '--restart' in sys.argv:
        print('Restarted:', runner.restart_server())
    elif '--status' in sys.argv:
        print('Healthy:', runner.is_healthy())
    else:
        print('Usage: python embedded_llm_runner.py [--start|--stop|--restart|--status]')


if __name__ == '__main__':
    main()
