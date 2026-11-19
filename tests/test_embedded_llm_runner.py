import subprocess
import sys
import time
from unittest.mock import MagicMock, patch

import pytest
import requests

from scripts.embedded_llm_runner import MODEL_URL, EmbeddedLLMRunner, assign_kill_on_close_job, close_job, main as runner_main

# Only the bundled model file is ever downloaded, so download tests use its file name.
BUNDLED_MODEL = MODEL_URL.rsplit('/', 1)[-1]


def spawn_sleeper():
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])


def test_job_object_kills_child_when_closed():
    child = spawn_sleeper()
    try:
        job = assign_kill_on_close_job(child)
        assert job
        assert child.poll() is None
        close_job(job)
        child.wait(timeout=10)
        assert child.poll() is not None
    finally:
        if child.poll() is None:
            child.kill()


def test_stop_only_touches_own_process():
    runner = EmbeddedLLMRunner()
    with patch("scripts.embedded_llm_runner.subprocess.run") as run:
        runner.stop_server()
    run.assert_not_called()


def test_stop_terminates_started_process():
    runner = EmbeddedLLMRunner()
    runner.process = spawn_sleeper()
    runner.job_object = assign_kill_on_close_job(runner.process)
    process = runner.process
    runner.stop_server()
    assert process.poll() is not None
    assert runner.process is None
    assert runner.job_object is None


def test_health_check_has_timeout_and_survives_errors():
    runner = EmbeddedLLMRunner()
    with patch("scripts.embedded_llm_runner.requests.get", side_effect=requests.ConnectionError()) as get:
        assert runner.is_healthy() is False
    assert get.call_args.kwargs.get("timeout")


def test_healthy_server_is_reused_without_launching():
    runner = EmbeddedLLMRunner()
    runner.is_healthy = MagicMock(return_value=True)
    with patch("scripts.embedded_llm_runner.subprocess.Popen") as popen:
        assert runner.start_server(wait_ready=False) is True
    popen.assert_not_called()


def test_missing_binary_reports_reason(tmp_path):
    runner = EmbeddedLLMRunner()
    runner.is_healthy = MagicMock(return_value=False)
    runner.bin_path = str(tmp_path / "llama-server.exe")
    assert runner.start_server(wait_ready=False) is False
    assert "llama-server" in runner.last_error


def test_second_start_does_not_launch_again(tmp_path):
    runner = EmbeddedLLMRunner()
    runner.is_healthy = MagicMock(return_value=False)
    runner.process = spawn_sleeper()
    try:
        with patch("scripts.embedded_llm_runner.subprocess.Popen") as popen:
            assert runner.start_server(wait_ready=False) is True
        popen.assert_not_called()
    finally:
        runner.process.kill()
        runner.process = None


def test_wait_stops_early_when_process_dies():
    runner = EmbeddedLLMRunner()
    runner.is_healthy = MagicMock(return_value=False)
    runner.process = subprocess.Popen([sys.executable, "-c", "pass"])
    runner.process.wait(timeout=20)
    started = time.time()
    assert runner.wait_for_ready(timeout=30) is False
    assert time.time() - started < 5
    assert runner.last_error
    runner.process = None


def test_launch_limits_threads_and_lowers_priority(tmp_path):
    runner = EmbeddedLLMRunner()
    runner.log_path = str(tmp_path / "logs" / "llama-server.log")
    with patch("scripts.embedded_llm_runner.subprocess.Popen") as popen, \
            patch("scripts.embedded_llm_runner.assign_kill_on_close_job", return_value=None):
        assert runner._launch() is True
    args = popen.call_args.args[0]
    threads = int(args[args.index("-t") + 1])
    assert 1 <= threads <= 4
    assert popen.call_args.kwargs["creationflags"] & 0x00004000
    runner._close_log()
    runner.process = None


def test_is_starting_is_true_only_while_starting(tmp_path):
    runner = EmbeddedLLMRunner()
    runner.is_healthy = MagicMock(return_value=False)
    runner.ensure_binaries_exist = MagicMock(return_value=True)
    runner.ensure_model_exists = MagicMock(return_value=True)
    runner._launch = MagicMock(return_value=True)
    seen = []

    def fake_wait(timeout=10):
        seen.append(runner.is_starting())
        return True

    runner.wait_for_ready = fake_wait
    assert runner.is_starting() is False
    assert runner.start_server(wait_ready=True) is True
    assert seen == [True]
    assert runner.is_starting() is False
    assert runner.state == "ready"

    runner.wait_for_ready = MagicMock(return_value=False)
    assert runner.start_server(wait_ready=True) is False
    assert runner.is_starting() is False
    assert runner.state == "failed"


def test_orchestrator_answers_immediately_while_model_loads():
    from scripts.llm_orchestrator import LLM_LOADING_MESSAGE, LLMOrchestrator
    orch = LLMOrchestrator.__new__(LLMOrchestrator)
    orch.runner = MagicMock()
    orch.runner.is_starting.return_value = True
    orch.runner.is_healthy.return_value = False
    orch.llama_server_url = "http://127.0.0.1:1/v1/chat/completions"
    started = time.time()
    with patch("scripts.llm_orchestrator.requests.post") as post:
        reply = orch._call_llm("system", "안녕")
    assert time.time() - started < 1
    # No model text: the guide falls back to its source and smalltalk shows the notice itself.
    assert reply is None and orch.llm_loading() is True
    assert "적재" in LLM_LOADING_MESSAGE
    orch.runner.wait_for_ready.assert_not_called()
    post.assert_not_called()


def test_failed_download_leaves_no_partial_file(tmp_path):
    runner = EmbeddedLLMRunner(model_path=str(tmp_path / BUNDLED_MODEL))
    with patch("scripts.embedded_llm_runner.requests.get", side_effect=requests.ConnectionError()):
        assert runner.ensure_model_exists() is False
    assert list(tmp_path.iterdir()) == []
    assert runner.last_error


def _run_download(tmp_path, **get_kwargs):
    with patch("scripts.embedded_llm_runner.get_path", lambda *p: str(tmp_path.joinpath(*p))),             patch.object(sys, "argv", ["embedded_llm_runner.py", "--download"]),             patch("scripts.embedded_llm_runner.requests.get", **get_kwargs) as get,             pytest.raises(SystemExit) as exit_info:
        runner_main()
    return exit_info.value.code, get


def test_download_flag_prints_progress_with_read_timeout_then_skips(tmp_path, capsys):
    response = MagicMock(headers={"content-length": "4"})
    response.iter_content.return_value = [b"ab", b"cd"]
    code, get = _run_download(tmp_path, return_value=response)
    out = capsys.readouterr().out
    assert code == 0 and get.call_args.kwargs["timeout"] == (15, 60)
    assert "50.0%" in out and "100.0%" in out and "MB" in out
    assert (tmp_path / "models" / "google_gemma-4-E2B-it-Q4_K_M.gguf").read_bytes() == b"abcd"
    with patch("scripts.embedded_llm_runner.MIN_MODEL_BYTES", 3):
        code, get = _run_download(tmp_path)
    assert code == 0 and not get.called and "[OK] Model already exists." in capsys.readouterr().out


def test_download_flag_exits_one_on_failure(tmp_path):
    assert _run_download(tmp_path, side_effect=requests.ReadTimeout())[0] == 1


def test_user_model_is_never_replaced_by_the_bundled_download(tmp_path):
    small = tmp_path / "qwen-0.5b.gguf"
    small.write_bytes(b"gguf")
    with patch("scripts.embedded_llm_runner.requests.get") as get:
        assert EmbeddedLLMRunner(model_path=str(small)).ensure_model_exists() is True
        missing = EmbeddedLLMRunner(model_path=str(tmp_path / "typo.gguf"))
        assert missing.ensure_model_exists() is False
    get.assert_not_called()
    assert small.read_bytes() == b"gguf"
    assert "typo.gguf" in missing.last_error


def _starting_runner(tmp_path):
    runner = EmbeddedLLMRunner(model_path=str(tmp_path / BUNDLED_MODEL))
    runner.is_healthy = MagicMock(return_value=False)
    runner.ensure_binaries_exist = MagicMock(return_value=True)
    return runner


def test_stop_during_model_download_cancels_the_start(tmp_path):
    import threading

    runner = _starting_runner(tmp_path)
    runner._launch = MagicMock(return_value=True)
    stop_done = threading.Event()

    def stopper():
        runner.stop_server()
        stop_done.set()

    def chunks():
        yield b"a" * 10
        threading.Thread(target=stopper, daemon=True).start()
        # stop_server raises the flag before it waits for the lock this download holds.
        for _ in range(200):
            if runner._stop_requested.is_set():
                break
            time.sleep(0.01)
        yield b"b" * 10
        yield b"c" * 10

    response = MagicMock(headers={"content-length": "30"})
    response.iter_content.return_value = chunks()
    started = time.time()
    with patch("scripts.embedded_llm_runner.requests.get", return_value=response):
        assert runner.start_server(wait_ready=True, timeout=30) is False
    assert stop_done.wait(timeout=5)
    assert time.time() - started < 4
    runner._launch.assert_not_called()
    assert list(tmp_path.iterdir()) == []
    assert runner.state == "idle" and runner.is_starting() is False


def test_start_after_a_stop_is_not_cancelled(tmp_path):
    runner = _starting_runner(tmp_path)
    runner.ensure_model_exists = MagicMock(return_value=True)
    runner._launch = MagicMock(return_value=True)
    runner.wait_for_ready = MagicMock(return_value=True)
    runner.stop_server()
    assert runner.start_server(wait_ready=True) is True
    runner._launch.assert_called_once()


def test_timed_out_start_terminates_the_server(tmp_path):
    runner = _starting_runner(tmp_path)
    runner.ensure_model_exists = MagicMock(return_value=True)
    launched = []

    def launch():
        runner.process = spawn_sleeper()
        launched.append(runner.process)
        return True

    runner._launch = launch
    runner.wait_for_ready = MagicMock(return_value=False)
    try:
        assert runner.start_server(wait_ready=True, timeout=1) is False
        launched[0].wait(timeout=10)
        assert launched[0].poll() is not None
        assert runner.process is None and runner.state == "failed"
    finally:
        if launched and launched[0].poll() is None:
            launched[0].kill()


def test_stop_ends_a_wait_for_ready_early(tmp_path):
    import threading

    runner = _starting_runner(tmp_path)
    runner.process = spawn_sleeper()
    result = []
    waiter = threading.Thread(target=lambda: result.append(runner.wait_for_ready(timeout=30)))
    started = time.time()
    waiter.start()
    time.sleep(0.3)
    runner.stop_server()
    waiter.join(timeout=10)
    assert result == [False]
    assert time.time() - started < 5


def test_binary_download_after_a_stop_still_runs(tmp_path):
    import io
    import zipfile

    runner = EmbeddedLLMRunner()
    runner.bin_path = str(tmp_path / "bin" / "llama-server.exe")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("build/llama-server.exe", b"exe")
    response = MagicMock(headers={"content-length": str(len(buf.getvalue()))})
    response.iter_content.return_value = [buf.getvalue()]
    runner.stop_server()
    with patch.object(runner, "_resolve_bin_url", return_value="http://example.invalid/x.zip"), \
            patch("scripts.embedded_llm_runner.requests.get", return_value=response):
        assert runner.download_binaries() is True
    assert (tmp_path / "bin" / "llama-server.exe").read_bytes() == b"exe"
