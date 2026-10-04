import errno
import json
import os
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta


DB_PATH = Path.home() / ".linux_ai_agent" / "agent.db"


def get_connection():
    DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row

    return connection

def initialize_database():
    connection = get_connection()

    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_request TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                command TEXT NOT NULL,
                approved INTEGER NOT NULL,
                return_code INTEGER,
                status TEXT NOT NULL DEFAULT 'PENDING',
                created_at TEXT NOT NULL,
                FOREIGN KEY (task_id)
                    REFERENCES tasks(id)
            );

            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                command_id INTEGER NOT NULL,
                output TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (command_id)
                    REFERENCES commands(id)
            );

            CREATE TABLE IF NOT EXISTS processes (
                command_id INTEGER PRIMARY KEY,
                pid INTEGER NOT NULL,
                process_group_id INTEGER NOT NULL,
                collector_pid INTEGER NOT NULL DEFAULT 0,
                monitor_pid INTEGER NOT NULL DEFAULT 0,
                log_path TEXT NOT NULL,
                status_path TEXT NOT NULL,
                collector_errors_path TEXT NOT NULL DEFAULT '',
                monitor_log_path TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT,
                status TEXT NOT NULL DEFAULT 'RUNNING',
                FOREIGN KEY (command_id)
                    REFERENCES commands(id)
            );
            """
        )

        process_columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(processes)"
            ).fetchall()
        }
        migrations = {
            "collector_pid": (
                "INTEGER NOT NULL DEFAULT 0"
            ),
            "monitor_pid": (
                "INTEGER NOT NULL DEFAULT 0"
            ),
            "collector_errors_path": (
                "TEXT NOT NULL DEFAULT ''"
            ),
            "monitor_log_path": (
                "TEXT NOT NULL DEFAULT ''"
            ),
            "created_at": (
                "TEXT NOT NULL DEFAULT ''"
            ),
            "completed_at": "TEXT",
        }
        for column, definition in migrations.items():
            if column not in process_columns:
                connection.execute(
                    f"ALTER TABLE processes ADD COLUMN {column} {definition}"
                )

        connection.commit()

    finally:
        connection.close()
def recover_stale_tasks(max_age_minutes=30):
    connection = get_connection()

    try:
        cutoff = (
            datetime.now()
            - timedelta(minutes=max_age_minutes)
        )

        connection.execute(
            """
            UPDATE tasks
            SET status = 'FAILED',
                updated_at = ?
            WHERE status = 'RUNNING'
              AND updated_at < ?
            """,
            (
                datetime.now().isoformat(),
                cutoff.isoformat(),
            ),
        )

        connection.commit()

    finally:
        connection.close()

def create_task(user_request):
    recover_stale_tasks()
    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            INSERT INTO tasks (
                user_request,
                status,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                user_request,
                "RUNNING",
                datetime.now().isoformat(),
                datetime.now().isoformat(),
            ),
        )

        connection.commit()

        return cursor.lastrowid

    finally:
        connection.close()


def update_task_status(task_id, status):
    connection = get_connection()

    try:
        connection.execute(
            """
            UPDATE tasks
            SET status = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                status,
                datetime.now().isoformat(),
                task_id,
            ),
        )

        connection.commit()

    finally:
        connection.close()


def add_command(task_id, command, approved, return_code=None, status="PENDING"):
    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            INSERT INTO commands (
                task_id,
                command,
                approved,
                return_code,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                command,
                int(approved),
                return_code,
                status,
                datetime.now().isoformat(),
            ),
        )

        connection.commit()
        return cursor.lastrowid

    finally:
        connection.close()


def add_result(command_id, output):
    connection = get_connection()

    try:
        connection.execute(
            """
            INSERT INTO results (
                command_id,
                output,
                created_at
            )
            VALUES (?, ?, ?)
            """,
            (
                command_id,
                output,
                datetime.now().isoformat(),
            ),
        )

        connection.commit()

    finally:
        connection.close()


def register_process(command_id, result, monitor_log_path=""):
    connection = get_connection()

    try:
        monitor_log_path = monitor_log_path or result["log_path"] + ".monitor"
        connection.execute(
            """
            INSERT INTO processes (
                command_id,
                pid,
                process_group_id,
                collector_pid,
                log_path,
                status_path,
                collector_errors_path,
                monitor_log_path,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                command_id,
                result["pid"],
                result["process_group_id"],
                result["collector_pid"],
                result["log_path"],
                result["status_path"],
                result["collector_errors_path"],
                monitor_log_path,
                datetime.now().isoformat(),
            ),
        )
        connection.commit()
        return monitor_log_path

    finally:
        connection.close()


def set_process_monitor(command_id, monitor_pid):
    connection = get_connection()

    try:
        connection.execute(
            """
            UPDATE processes
            SET monitor_pid = ?
            WHERE command_id = ?
            """,
            (monitor_pid, command_id),
        )
        connection.commit()

    finally:
        connection.close()


def _process_group_exists(process_group_id):
    try:
        os.killpg(process_group_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError as error:
        if error.errno == errno.ESRCH:
            return False
        raise

    proc_path = Path("/proc")
    if not proc_path.is_dir():
        return True

    inaccessible_process = False
    for process_path in proc_path.iterdir():
        if not process_path.name.isdecimal():
            continue

        try:
            stat_fields = (
                process_path.joinpath("stat")
                .read_text(encoding="utf-8")
                .rsplit(")", 1)[1]
                .split()
            )
        except FileNotFoundError:
            continue
        except PermissionError:
            inaccessible_process = True
            continue

        if len(stat_fields) < 3:
            continue

        state = stat_fields[0]
        process_group = int(stat_fields[2])
        if process_group == process_group_id and state != "Z":
            return True

    return inaccessible_process


def _read_process_output(log_path):
    if not Path(log_path).exists():
        return "[process log was removed by the retention policy]"

    with open(log_path, encoding="utf-8", errors="replace") as output_file:
        output = output_file.read(12001)

    if len(output) > 12000:
        return output[:12000] + "\n...[output truncated]"
    return output


def _process_exists(pid):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError as error:
        if error.errno == errno.ESRCH:
            return False
        raise

    stat_path = Path("/proc") / str(pid) / "stat"
    if stat_path.exists():
        fields = stat_path.read_text(encoding="utf-8").rsplit(")", 1)[1].split()
        return bool(fields) and fields[0] != "Z"
    return True


def refresh_process(command_id):
    connection = get_connection()

    try:
        row = connection.execute(
            """
            SELECT
                p.command_id,
                p.pid,
                p.process_group_id,
                p.collector_pid,
                p.monitor_pid,
                p.log_path,
                p.status_path,
                p.collector_errors_path,
                p.monitor_log_path,
                p.status
            FROM processes p
            WHERE p.command_id = ?
            """,
            (command_id,),
        ).fetchone()

        if row is None:
            return None
        if row["status"] != "RUNNING":
            return row["status"]

        status_path = Path(row["status_path"])
        return_code = None
        command_exited = status_path.exists()
        if command_exited:
            status_text = status_path.read_text(encoding="utf-8").strip()
            try:
                return_code = int(status_text)
            except ValueError as error:
                raise ValueError(
                    f"Invalid exit status in {status_path}: {status_text!r}"
                ) from error

        group_exists = _process_group_exists(row["process_group_id"])
        collector_exists = _process_exists(row["collector_pid"])
        if group_exists:
            if row["monitor_pid"] and not _process_exists(row["monitor_pid"]):
                monitor_log_path = row["monitor_log_path"]
                monitor_errors = ""
                if monitor_log_path and Path(monitor_log_path).exists():
                    monitor_errors = Path(monitor_log_path).read_text(
                        encoding="utf-8"
                    )
                detail = monitor_errors or "monitor exited unexpectedly"
                raise RuntimeError(
                    f"Process monitor failed for command {command_id}: "
                    f"{detail}"
                )
            process_status = "RUNNING"
            command_status = "RUNNING"
        elif collector_exists:
            process_status = "RUNNING"
            command_status = "RUNNING"
        elif command_exited:
            process_status = "EXITED"
            command_status = "SUCCESS" if return_code == 0 else "FAILED"
        else:
            process_status = "STOPPED"
            command_status = "STOPPED"

        output = _read_process_output(row["log_path"])
        collector_errors_path = row["collector_errors_path"]
        if collector_errors_path and Path(collector_errors_path).exists():
            collector_errors = Path(collector_errors_path).read_text(
                encoding="utf-8"
            )
            if collector_errors:
                raise RuntimeError(
                    "Output collector failed: " + collector_errors
                )

        process_result = {
            "running": process_status == "RUNNING",
            "pid": row["pid"],
            "process_group_id": row["process_group_id"],
            "log_path": row["log_path"],
            "return_code": return_code,
            "output": output,
        }

        connection.execute(
            """
            UPDATE processes
            SET status = ?, completed_at = ?
            WHERE command_id = ?
            """,
            (
                process_status,
                (
                    datetime.now().isoformat()
                    if process_status != "RUNNING"
                    else None
                ),
                command_id,
            ),
        )
        connection.execute(
            """
            UPDATE commands
            SET status = ?, return_code = ?
            WHERE id = ?
            """,
            (command_status, return_code, command_id),
        )
        connection.execute(
            """
            UPDATE results
            SET output = ?
            WHERE command_id = ?
            """,
            (json.dumps(process_result, indent=2), command_id),
        )

        connection.commit()
        if process_status != "RUNNING":
            status_path.unlink(missing_ok=True)
            if collector_errors_path:
                Path(collector_errors_path).unlink(missing_ok=True)
        return process_status

    finally:
        connection.close()


def _refresh_running_processes(task_id):
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT p.command_id
            FROM processes p
            JOIN commands c ON c.id = p.command_id
            WHERE c.task_id = ?
              AND p.status = 'RUNNING'
            """,
            (task_id,),
        ).fetchall()
    finally:
        connection.close()

    for row in rows:
        refresh_process(row["command_id"])


def cleanup_expired_process_logs(retention_days=7):
    cutoff = datetime.now() - timedelta(days=retention_days)
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT
                p.log_path,
                p.collector_errors_path,
                p.monitor_log_path
            FROM processes p
            JOIN commands c ON c.id = p.command_id
            WHERE p.status != 'RUNNING'
              AND coalesce(
                    nullif(p.completed_at, ''),
                    nullif(p.created_at, ''),
                    c.created_at
                  ) < ?
            """,
            (cutoff.isoformat(),),
        ).fetchall()
    finally:
        connection.close()

    for row in rows:
        for path in (
            row["log_path"],
            row["collector_errors_path"],
            row["monitor_log_path"],
        ):
            if path:
                Path(path).unlink(missing_ok=True)


def get_task_history(task_id, limit=2):
    _refresh_running_processes(task_id)
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT
                c.id AS command_id,
                c.command,
                c.approved,
                c.return_code,
                c.status,
                r.output,
                p.pid,
                p.process_group_id,
                p.log_path,
                p.monitor_log_path
            FROM commands c
            LEFT JOIN results r
                ON r.command_id = c.id
            LEFT JOIN processes p
                ON p.command_id = c.id
            WHERE c.task_id = ?
            ORDER BY c.id DESC
            LIMIT ?
            """,
            (task_id, limit),
        ).fetchall()

        return [dict(row) for row in reversed(rows)]

    finally:
        connection.close()

if __name__ == "__main__":
    initialize_database()
    print(f"Database initialized: {DB_PATH}")