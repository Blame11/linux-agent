import subprocess
import sys
import time
from pathlib import Path

from .executor import PROJECT_ROOT
from . import task_state


MONITOR_INTERVAL_SECONDS = 1


def start_process_monitor(command_id, monitor_log_path):
    Path(monitor_log_path).parent.mkdir(
        mode=0o700,
        parents=True,
        exist_ok=True
    )
    with open(monitor_log_path, "w", encoding="utf-8") as monitor_log:
        return subprocess.Popen(
            [
                sys.executable,
                "-m",
                "backend.process_monitor",
                str(command_id),
                str(task_state.DB_PATH),
            ],
            cwd=PROJECT_ROOT,
            stdin=subprocess.DEVNULL,
            stdout=monitor_log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )


def monitor_process(command_id):
    next_cleanup = 0
    while True:
        if time.monotonic() >= next_cleanup:
            task_state.cleanup_expired_process_logs()
            next_cleanup = time.monotonic() + 60

        status = task_state.refresh_process(command_id)
        if status != "RUNNING":
            task_state.cleanup_expired_process_logs()
            return
        time.sleep(MONITOR_INTERVAL_SECONDS)


def main():
    if len(sys.argv) != 3:
        raise SystemExit(
            "usage: process_monitor.py COMMAND_ID DATABASE_PATH"
        )

    task_state.DB_PATH = Path(sys.argv[2])
    monitor_process(int(sys.argv[1]))


if __name__ == "__main__":
    main()
