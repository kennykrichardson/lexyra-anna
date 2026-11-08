#!/usr/bin/env python3
"""Protocol-aware offline smoke test for the packaged Linux Executa."""
from __future__ import annotations

import json
import selectors
import subprocess
import sys


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: smoke-linux-binary.py PATH_TO_EXECUTA")
    proc = subprocess.Popen(
        [sys.argv[1]], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1,
    )
    assert proc.stdin is not None and proc.stdout is not None
    selector = selectors.DefaultSelector()
    selector.register(proc.stdout, selectors.EVENT_READ)

    def send(frame: dict) -> None:
        proc.stdin.write(json.dumps(frame, separators=(",", ":")) + "\n")
        proc.stdin.flush()

    def receive(timeout: float = 15.0) -> dict:
        if not selector.select(timeout):
            raise TimeoutError("timed out waiting for Executa stdout")
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError("Executa closed stdout unexpectedly")
        return json.loads(line)

    try:
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2.0",
            "capabilities": {"sampling": {}},
            "clientInfo": {"name": "lexyra-linux-smoke", "version": "1"},
        }})
        initialized = receive()
        assert initialized["id"] == 1
        assert initialized["result"]["protocolVersion"] == "2.0"
        assert initialized["result"]["capabilities"] == {"sampling": {}}

        send({"jsonrpc": "2.0", "id": 2, "method": "describe"})
        described = receive()
        assert described["id"] == 2
        assert "llm.sample" in described["result"]["host_capabilities"]
        assert "enhance" in [tool["name"] for tool in described["result"]["tools"]]

        send({"jsonrpc": "2.0", "id": 3, "method": "invoke", "params": {
            "tool": "enhance",
            "arguments": {"text": "A Linux packaged smoke check.", "style": "concise"},
            "context": {"invoke_id": "linux-smoke-invoke", "sampling_token": "offline-fixture-token"},
        }})
        sampling = receive()
        assert sampling["method"] == "sampling/createMessage"
        assert sampling["params"]["includeContext"] == "none"
        assert sampling["params"]["metadata"] == {"executa_invoke_id": "linux-smoke-invoke"}
        assert sampling["params"]["messages"][0]["content"]["text"] == "A Linux packaged smoke check."
        send({"jsonrpc": "2.0", "id": sampling["id"], "result": {
            "role": "assistant",
            "content": {"type": "text", "text": "Packaged protocol smoke passed."},
            "stopReason": "endTurn",
        }})
        invoked = receive()
        assert invoked["id"] == 3
        assert invoked["result"]["success"] is True
        assert invoked["result"]["data"] == {
            "enhanced_text": "Packaged protocol smoke passed.", "style": "concise"
        }

        send({"jsonrpc": "2.0", "id": 4, "method": "health"})
        health = receive()
        assert health["id"] == 4 and health["result"]["status"] == "healthy"

        proc.stdin.close()
        code = proc.wait(timeout=10)
        stderr = proc.stderr.read() if proc.stderr else ""
        assert code == 0, f"binary exited with {code}; stderr={stderr!r}"
        assert not stderr, f"unexpected stderr from smoke run: {stderr!r}"
        print("Packaged Linux x86_64 Executa passed initialize, describe, mocked reverse Sampling, invoke, health, and EOF checks.")
        return 0
    finally:
        selector.close()
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
