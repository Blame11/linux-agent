import os
import subprocess
import sys


def test_ai_context_runs_without_groq_configuration():
    env = os.environ.copy()
    env.pop("GROQ_API_KEY", None)
    env.pop("GROQ_MODEL", None)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from backend.cli import ai_context; ai_context()",
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Linux AI Context" in result.stdout
    assert "GROQ_API_KEY is not configured" not in result.stderr
