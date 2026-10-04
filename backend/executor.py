import subprocess
import tempfile

MAX_OUTPUT = 12000
COMMAND_STARTUP_TIMEOUT = 5


def execute_command(command):
    command = command.strip()

    if not command:
        return {
            "success": False,
            "error": "Empty command."
        }

    try:
        # Use a temporary file instead of PIPE.
        #
        # Background processes can inherit stdout/stderr without keeping
        # subprocess.PIPE open indefinitely.
        with tempfile.TemporaryFile(
            mode="w+",
            encoding="utf-8"
        ) as output_file:

            process = subprocess.Popen(
                command,
                shell=True,
                executable="/bin/bash",
                stdout=output_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )

            try:
                return_code = process.wait(
                    timeout=COMMAND_STARTUP_TIMEOUT
                )
            except subprocess.TimeoutExpired:
                if process.poll() is None:
                    output_file.seek(0)
                    output = output_file.read()

                    if len(output) > MAX_OUTPUT:
                        output = (
                            output[:MAX_OUTPUT]
                            + "\n...[output truncated]"
                        )

                    return {
                        "success": True,
                        "running": True,
                        "pid": process.pid,
                        "return_code": None,
                        "output": output,
                        "message": (
                            "Command is still running; it was left running "
                            f"in the background (PID {process.pid})."
                        )
                    }

                return_code = process.returncode

            output_file.seek(0)
            output = output_file.read()

        if len(output) > MAX_OUTPUT:
            output = (
                output[:MAX_OUTPUT]
                + "\n...[output truncated]"
            )

        return {
            "success": return_code == 0,
            "running": False,
            "return_code": return_code,
            "output": output
        }

    except Exception as error:
        return {
            "success": False,
            "error": str(error)
        }