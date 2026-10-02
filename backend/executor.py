import subprocess

MAX_OUTPUT = 12000
COMMAND_TIMEOUT = 300


def execute_command(command):
    command = command.strip()

    if not command:
        return {
            "success": False,
            "error": "Empty command."
        }

    try:
        result = subprocess.run(
            command,
            shell=True,
            executable="/bin/bash",
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT,
        )

        output = result.stdout

        if result.stderr:
            if output:
                output += "\n"
            output += result.stderr

        if len(output) > MAX_OUTPUT:
            output = (
                output[:MAX_OUTPUT]
                + "\n...[output truncated]"
            )

        return {
            "success": result.returncode == 0,
            "return_code": result.returncode,
            "output": output
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Command timed out after {COMMAND_TIMEOUT} seconds."
        }

    except Exception as error:
        return {
            "success": False,
            "error": str(error)
        }
