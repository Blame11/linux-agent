import os
import shlex
import signal
import socket
import sys
import time
import urllib.request

from backend.executor import execute_command


def test_persistent_http_server_returns_running_pid():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]

    command = (
        f"{shlex.quote(sys.executable)} -m http.server {port} "
        "--bind 127.0.0.1"
    )
    started_at = time.monotonic()

    result = execute_command(command)

    assert time.monotonic() - started_at < 8
    assert result["success"] is True
    assert result["running"] is True
    assert result["return_code"] is None
    assert isinstance(result["pid"], int)
    assert "background" in result["message"]

    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}",
            timeout=2
        ) as response:
            assert response.status == 200
    finally:
        try:
            os.killpg(result["pid"], signal.SIGTERM)
        except ProcessLookupError:
            pass


def test_completed_command_returns_exit_code_and_output():
    result = execute_command("printf 'done' && exit 7")

    assert result["success"] is False
    assert result["running"] is False
    assert result["return_code"] == 7
    assert result["output"] == "done"
