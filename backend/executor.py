import os
import subprocess
import sys
import tempfile
from pathlib import Path

MAX_OUTPUT = 12000
COMMAND_STARTUP_TIMEOUT = 5
PROCESS_LOG_DIR = Path.home() / ".linux_ai_agent" / "processes"
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _read_output(log_path):
    with open(log_path, encoding="utf-8", errors="replace") as output_file:
        output = output_file.read(MAX_OUTPUT + 1)

    if len(output) > MAX_OUTPUT:
        return output[:MAX_OUTPUT] + "\n...[output truncated]"
    return output


def _remove_process_files(*file_paths):
    for file_path in file_paths:
        if not file_path:
            continue
        try:
            os.unlink(file_path)
        except FileNotFoundError:
            pass


def execute_command(command):
    command = command.strip()

    if not command:
        return {
            "success": False,
            "error": "Empty command."
        }

    log_path = None
    status_path = None
    collector = None
    pipe_read = None
    pipe_write = None

    try:
        PROCESS_LOG_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=PROCESS_LOG_DIR,
            prefix="command-",
            suffix=".log",
            delete=False
        ) as output_file:
            log_path = output_file.name

        status_fd, status_path = tempfile.mkstemp(
            dir=PROCESS_LOG_DIR,
            prefix="command-",
            suffix=".status"
        )
        os.close(status_fd)
        os.unlink(status_path)

        pipe_read, pipe_write = os.pipe()
        collector_errors_path = f"{log_path}.collector-errors"
        with open(collector_errors_path, "w", encoding="utf-8") as errors_file:
            collector = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "backend.output_collector",
                    str(pipe_read),
                    log_path,
                ],
                cwd=PROJECT_ROOT,
                pass_fds=(pipe_read,),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=errors_file,
                start_new_session=True,
            )
        os.close(pipe_read)
        pipe_read = None

        wrapper = (
            'command_text=$1; status_file=$2; '
            '/bin/bash -c "$command_text"; command_status=$?; '
            'status_tmp="${status_file}.$$"; '
            'printf "%s\\n" "$command_status" > "$status_tmp" && '
            'mv "$status_tmp" "$status_file"; '
            'exit "$command_status"'
        )

        process = subprocess.Popen(
            [
                "/bin/bash",
                "-c",
                wrapper,
                "linux-ai-agent",
                command,
                status_path,
            ],
            stdout=pipe_write,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        os.close(pipe_write)
        pipe_write = None

        try:
            return_code = process.wait(timeout=COMMAND_STARTUP_TIMEOUT)
        except subprocess.TimeoutExpired:
            if process.poll() is None:
                output = _read_output(log_path)
                return {
                    "success": True,
                    "running": True,
                    "pid": process.pid,
                    "process_group_id": process.pid,
                    "collector_pid": collector.pid,
                    "log_path": log_path,
                    "status_path": status_path,
                    "collector_errors_path": collector_errors_path,
                    "return_code": None,
                    "output": output,
                    "message": (
                        "Command is still running; it was left running "
                        f"in the background (PID {process.pid}, process "
                        f"group {process.pid}). Output is being saved to "
                        f"{log_path} (maximum 1 MiB)."
                    )
                }

            return_code = process.returncode

        try:
            collector.wait(timeout=2)
        except subprocess.TimeoutExpired:
            if not Path(collector_errors_path).stat().st_size == 0:
                raise RuntimeError(
                    Path(collector_errors_path).read_text(encoding="utf-8")
                )
            output = _read_output(log_path)
            return {
                "success": return_code == 0,
                "running": True,
                "pid": process.pid,
                "process_group_id": process.pid,
                "collector_pid": collector.pid,
                "log_path": log_path,
                "status_path": status_path,
                "collector_errors_path": collector_errors_path,
                "return_code": return_code,
                "output": output,
                "message": (
                    "Command exited, but its output stream is still open. "
                    f"Output is being saved to {log_path} (maximum 1 MiB)."
                )
            }

        collector_errors = Path(collector_errors_path).read_text(
            encoding="utf-8"
        )
        if collector_errors:
            raise RuntimeError(collector_errors)

        output = _read_output(log_path)
        _remove_process_files(
            log_path,
            status_path,
            collector_errors_path
        )

        return {
            "success": return_code == 0,
            "running": False,
            "return_code": return_code,
            "output": output
        }

    except Exception as error:
        if collector is not None and collector.poll() is None:
            collector.terminate()
            collector.wait()
        if pipe_read is not None:
            os.close(pipe_read)
        if pipe_write is not None:
            os.close(pipe_write)
        _remove_process_files(
            log_path,
            status_path,
            f"{log_path}.collector-errors" if log_path else None
        )
        return {
            "success": False,
            "error": str(error)
        }