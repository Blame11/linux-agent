import shlex
import subprocess

from command_safety import classify_command


MAX_OUTPUT = 12000
COMMAND_TIMEOUT = 30


def execute_command(command):
    classification = classify_command(command)

    if classification == "UNKNOWN":
        return {
            "success": False,
            "error": "Command rejected by safety policy."
        }

    if classification == "DANGEROUS":
        return {
            "success": False,
            "error": "Dangerous commands are not executable yet."
        }

    try:
        args = shlex.split(command)

        if not args:
            return {
                "success": False,
                "error": "Empty command."
            }

        if args[0] == "sudo":
            return {
                "success": False,
                "error": "sudo execution is not enabled yet."
            }

        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT,
            shell=False,
        )

        output = result.stdout

        if result.stderr:
            output += result.stderr

        if not output:
            output = "(no output)"

        if len(output) > MAX_OUTPUT:
            output = output[:MAX_OUTPUT] + "\n...[output truncated]"

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

    except FileNotFoundError:
        return {
            "success": False,
            "error": "Executable not found."
        }

    except Exception as error:
        return {
            "success": False,
            "error": str(error)
        }