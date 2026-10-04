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
            """
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


def get_task_history(task_id, limit=2):
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
                r.output
            FROM commands c
            LEFT JOIN results r
                ON r.command_id = c.id
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