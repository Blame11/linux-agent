import subprocess


MAX_OUTPUT = 12000
COMMAND_TIMEOUT = 30


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
            timeout=COMMAND_TIMEOUT,
        )

        return {
            "success": result.returncode == 0,
            "return_code": result.returncode,
            "output": "(command completed; output was displayed in the terminal)"
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