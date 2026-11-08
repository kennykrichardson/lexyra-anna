import json
import subprocess
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1] / "lexyra_writer_plugin.py"


def test_stdio_initialize_describe_health_and_invalid_input():
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2.0"}},
        {"jsonrpc": "2.0", "id": 2, "method": "describe"},
        {"jsonrpc": "2.0", "id": 3, "method": "health"},
        {"jsonrpc": "2.0", "id": 4, "method": "invoke", "params": {"tool": "enhance", "arguments": {"text": " ", "style": "professional"}}},
    ]
    run = subprocess.run(
        [sys.executable, str(PLUGIN)],
        input="".join(json.dumps(request) + "\n" for request in requests),
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    frames = [json.loads(line) for line in run.stdout.splitlines()]
    by_id = {frame["id"]: frame["result"] for frame in frames}
    assert by_id[1]["protocolVersion"] == "2.0"
    assert by_id[1]["capabilities"] == {"sampling": {}}
    assert "client_capabilities" not in by_id[1]
    assert [tool["name"] for tool in by_id[2]["tools"]] == ["enhance"]
    assert by_id[3]["status"] == "healthy"
    assert by_id[4]["success"] is False
    assert "blank" in by_id[4]["error"]
    assert run.stderr == ""
