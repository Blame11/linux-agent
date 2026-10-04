import json

from backend import agent
from backend.action import parse_ai_response


def test_parses_json_command_action():
    assert parse_ai_response(
        '{"action":"command","command":"printf ok"}'
    ) == {
        "action": "command",
        "command": "printf ok"
    }


def test_parses_execute_bash_tool_call_format():
    response = """<tool_call>
function=execute_bash>
python3 -m http.server 8000
</tool_call>"""

    assert parse_ai_response(response) == {
        "action": "command",
        "command": "python3 -m http.server 8000"
    }


def test_parses_json_execute_bash_tool_call():
    response = """<tool_call>
{"name":"execute_bash","arguments":{"command":"ls -la"}}
</tool_call>"""

    assert parse_ai_response(response) == {
        "action": "command",
        "command": "ls -la"
    }


def test_parses_embedded_json_command_action():
    response = 'Proposed command: {"action":"command","command":"pwd"}'

    assert parse_ai_response(response) == {
        "action": "command",
        "command": "pwd"
    }


def test_plain_text_is_returned_as_an_answer():
    assert parse_ai_response("The requested check is complete.") == {
        "action": "answer",
        "content": "The requested check is complete."
    }


def test_malformed_or_unsupported_tool_calls_are_rejected():
    assert parse_ai_response('{"action":"command","command":') is None
    assert parse_ai_response(
        "<tool_call>function=other_tool>\nwhoami\n</tool_call>"
    ) is None


def test_tool_call_command_still_requires_approval(monkeypatch):
    action = parse_ai_response(
        "<tool_call>function=execute_bash>\nprintf approved</tool_call>"
    )
    executor_calls = []

    monkeypatch.setattr(agent, "request_approval", lambda *_: False)
    monkeypatch.setattr(
        agent,
        "execute_command",
        lambda command: executor_calls.append(command)
    )

    result = agent.process_action(json.dumps(action))

    assert result["type"] == "cancelled"
    assert executor_calls == []
