import subprocess
import sys
import time
from unittest.mock import MagicMock, patch

import pytest
import requests

from scripts.embedded_llm_runner import EmbeddedLLMRunner, assign_kill_on_close_job, close_job


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


def test_failed_download_leaves_no_partial_file(tmp_path):
    runner = EmbeddedLLMRunner(model_path=str(tmp_path / "m.gguf"))
    with patch("scripts.embedded_llm_runner.requests.get", side_effect=requests.ConnectionError()):
        assert runner.ensure_model_exists() is False
    assert list(tmp_path.iterdir()) == []
    assert runner.last_error
