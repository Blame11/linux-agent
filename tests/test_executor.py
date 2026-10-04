import os
import shlex
import signal
import socket
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from backend import task_state
from backend.executor import execute_command
from backend.process_monitor import start_process_monitor


@pytest.fixture
def process_database(tmp_path, monkeypatch):
    monkeypatch.setattr(task_state, "DB_PATH", tmp_path / "agent.db")
    monkeypatch.setattr(
        "backend.executor.PROCESS_LOG_DIR",
        tmp_path / "processes"
    )
    task_state.initialize_database()
    return task_state.create_task("test command process")


def test_persistent_http_server_returns_running_pid(process_database):
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

    command_id = task_state.add_command(
        process_database,
        command,
        True,
        result["return_code"],
        "RUNNING"
    )
    task_state.add_result(command_id, result["output"])
    monitor_log = task_state.register_process(command_id, result)
    monitor = start_process_monitor(command_id, monitor_log)
    task_state.set_process_monitor(command_id, monitor.pid)

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
        deadline = time.monotonic() + 3
        status = "RUNNING"
        while status == "RUNNING" and time.monotonic() < deadline:
            connection = task_state.get_connection()
            try:
                row = connection.execute(
                    "SELECT status FROM commands WHERE id = ?",
                    (command_id,)
                ).fetchone()
            finally:
                connection.close()
            status = row["status"]
            if status == "RUNNING":
                time.sleep(0.1)

        assert status == "STOPPED"


def test_completed_command_returns_exit_code_and_output():
    result = execute_command("printf 'done' && exit 7")

    assert result["success"] is False
    assert result["running"] is False
    assert result["return_code"] == 7
    assert result["output"] == "done"


def test_long_finite_command_refreshes_exit_status_and_final_output(
    process_database
):
    result = execute_command("sleep 5.3; printf finished")
    assert result["running"] is True

    command_id = task_state.add_command(
        process_database,
        "sleep 5.3; printf finished",
        True,
        result["return_code"],
        "RUNNING"
    )
    task_state.add_result(command_id, "initial output")
    monitor_log = task_state.register_process(command_id, result)
    monitor = start_process_monitor(command_id, monitor_log)
    task_state.set_process_monitor(command_id, monitor.pid)

    deadline = time.monotonic() + 5
    status = "RUNNING"
    while status == "RUNNING" and time.monotonic() < deadline:
        connection = task_state.get_connection()
        try:
            row = connection.execute(
                "SELECT status FROM commands WHERE id = ?",
                (command_id,)
            ).fetchone()
        finally:
            connection.close()
        status = row["status"]
        if status == "RUNNING":
            time.sleep(0.1)

    assert status == "SUCCESS"
    completed_history = task_state.get_task_history(process_database)

    assert completed_history[0]["status"] == "SUCCESS"
    assert completed_history[0]["return_code"] == 0
    assert "finished" in completed_history[0]["output"]


def test_stopped_process_group_is_recorded_as_stopped(process_database):
    result = execute_command("sleep 30")
    assert result["running"] is True

    command_id = task_state.add_command(
        process_database,
        "sleep 30",
        True,
        result["return_code"],
        "RUNNING"
    )
    task_state.add_result(command_id, "initial output")
    task_state.register_process(command_id, result)

    os.killpg(result["process_group_id"], signal.SIGTERM)
    deadline = time.monotonic() + 3
    history = task_state.get_task_history(process_database)
    while history[0]["status"] == "RUNNING" and time.monotonic() < deadline:
        time.sleep(0.1)
        history = task_state.get_task_history(process_database)

    assert history[0]["status"] == "STOPPED"
    assert history[0]["return_code"] is None


def test_output_log_is_capped_and_marked(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "backend.executor.PROCESS_LOG_DIR",
        tmp_path / "processes"
    )
    monkeypatch.setattr(task_state, "DB_PATH", tmp_path / "agent.db")
    task_state.initialize_database()
    task_id = task_state.create_task("test bounded output")

    result = execute_command("head -c 2097152 /dev/zero; sleep 30")

    assert result["running"] is True
    assert os.path.getsize(result["log_path"]) <= 1024 * 1024
    assert b"output log truncated at 1 MiB" in Path(
        result["log_path"]
    ).read_bytes()

    command_id = task_state.add_command(
        task_id,
        "head -c 2097152 /dev/zero; sleep 30",
        True,
        None,
        "RUNNING"
    )
    task_state.add_result(command_id, "initial output")
    monitor_log = task_state.register_process(command_id, result)
    monitor = start_process_monitor(command_id, monitor_log)
    task_state.set_process_monitor(command_id, monitor.pid)

    os.killpg(result["process_group_id"], signal.SIGTERM)
    deadline = time.monotonic() + 3
    status = "RUNNING"
    while status == "RUNNING" and time.monotonic() < deadline:
        connection = task_state.get_connection()
        try:
            row = connection.execute(
                "SELECT status FROM commands WHERE id = ?",
                (command_id,)
            ).fetchone()
        finally:
            connection.close()
        status = row["status"]
        if status == "RUNNING":
            time.sleep(0.1)

    assert status == "STOPPED"


def test_cleanup_removes_completed_logs_after_retention(tmp_path, monkeypatch):
    monkeypatch.setattr(task_state, "DB_PATH", tmp_path / "agent.db")
    task_state.initialize_database()
    task_id = task_state.create_task("test log cleanup")
    command_id = task_state.add_command(
        task_id,
        "sleep 1",
        True,
        0,
        "SUCCESS"
    )
    log_paths = [tmp_path / name for name in ("output.log", "monitor.log")]
    for path in log_paths:
        path.write_text("test output", encoding="utf-8")

    task_state.register_process(
        command_id,
        {
            "pid": 1,
            "process_group_id": 1,
            "collector_pid": 2,
            "log_path": str(log_paths[0]),
            "status_path": str(tmp_path / "status"),
            "collector_errors_path": str(tmp_path / "collector-errors"),
        },
        str(log_paths[1])
    )
    connection = task_state.get_connection()
    try:
        old_timestamp = time.strftime(
            "%Y-%m-%dT%H:%M:%S",
            time.localtime(time.time() - 8 * 24 * 60 * 60)
        )
        connection.execute(
            """
            UPDATE processes
            SET status = 'EXITED', created_at = ?, completed_at = ?
            WHERE command_id = ?
            """,
            (
                old_timestamp,
                time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
                command_id,
            )
        )
        connection.commit()
    finally:
        connection.close()

    task_state.cleanup_expired_process_logs()
    assert all(path.exists() for path in log_paths)

    connection = task_state.get_connection()
    try:
        connection.execute(
            """
            UPDATE processes
            SET completed_at = ?
            WHERE command_id = ?
            """,
            (old_timestamp, command_id),
        )
        connection.commit()
    finally:
        connection.close()

    task_state.cleanup_expired_process_logs()

    assert all(not path.exists() for path in log_paths)
