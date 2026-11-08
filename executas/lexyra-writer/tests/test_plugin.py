import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lexyra_writer_plugin as plugin


def test_all_styles_are_in_prompt():
    for style in plugin.VALID_STYLES:
        system, messages = plugin.build_messages("Rough words", style)
        assert f"Selected style: {style}." in system
        assert messages[0]["content"]["text"] == "Rough words"
        assert "Never invent credentials" in system


def test_invalid_input_is_rejected():
    for text, style in [(" \n ", "professional"), ("x" * 10001, "professional"), ("text", "unknown")]:
        try:
            plugin.build_messages(text, style)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid input should be rejected")


def test_model_output_must_be_nonempty(monkeypatch):
    def fake_sample(system_prompt, messages, invoke_id):
        return {"content": {"type": "text", "text": "  "}}
    monkeypatch.setattr(plugin, "sample_message", fake_sample)
    try:
        plugin.enhance("Input", "professional", "invoke-1")
    except ValueError as exc:
        assert "empty or malformed" in str(exc)
    else:
        raise AssertionError("empty model output should be rejected")


def test_model_output_is_returned_for_requested_style(monkeypatch):
    monkeypatch.setattr(
        plugin,
        "sample_message",
        lambda system, messages, invoke_id: {"content": {"type": "text", "text": " Polished result. "}},
    )
    assert plugin.enhance("Original", "academic", "invoke-1") == {
        "enhanced_text": "Polished result.",
        "style": "academic",
    }


def test_truncated_model_output_is_rejected(monkeypatch):
    monkeypatch.setattr(
        plugin,
        "sample_message",
        lambda system, messages, invoke_id: {
            "content": {"type": "text", "text": "Partial result"},
            "stopReason": "maxTokens",
        },
    )
    try:
        plugin.enhance("Original", "concise", "invoke-1")
    except ValueError as exc:
        assert "incomplete" in str(exc)
    else:
        raise AssertionError("truncated model output should be rejected")


def test_sampling_requires_protocol_v2(monkeypatch):
    plugin._sampling_enabled = False
    try:
        plugin.sample_message("system", [], "invoke-1")
    except RuntimeError as exc:
        assert "protocol 2.0" in str(exc)
    else:
        raise AssertionError("sampling must be rejected before v2 negotiation")


def test_sampling_is_not_enabled_when_initialize_omits_version():
    from concurrent.futures import ThreadPoolExecutor
    import io

    old_stdout = sys.stdout
    try:
        sys.stdout = io.StringIO()
        with ThreadPoolExecutor(max_workers=1) as workers:
            plugin.dispatch({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}, workers)
        result = json.loads(sys.stdout.getvalue())["result"]
    finally:
        sys.stdout = old_stdout
    assert result["protocolVersion"] == "1.1"
    assert result["capabilities"] == {}
    assert plugin._sampling_enabled is False


def test_initialize_v2_advertises_host_sampling_capability():
    from concurrent.futures import ThreadPoolExecutor
    import io

    old_stdout = sys.stdout
    try:
        sys.stdout = io.StringIO()
        with ThreadPoolExecutor(max_workers=1) as workers:
            plugin.dispatch({"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {"protocolVersion": "2.0"}}, workers)
        result = json.loads(sys.stdout.getvalue())["result"]
    finally:
        sys.stdout = old_stdout
    assert result["protocolVersion"] == "2.0"
    assert result["capabilities"] == {"sampling": {}}
    assert result["server_info"]["name"] == plugin.MANIFEST["display_name"]


def test_reverse_sampling_request_matches_host_contract(monkeypatch):
    plugin._sampling_enabled = True
    captured = {}

    def fake_write(frame):
        captured.update(frame)
        plugin.dispatch_response({
            "jsonrpc": "2.0",
            "id": frame["id"],
            "result": {"content": {"type": "text", "text": "result"}},
        })

    monkeypatch.setattr(plugin, "write_frame", fake_write)
    result = plugin.sample_message(
        "system prompt",
        [{"role": "user", "content": {"type": "text", "text": "draft"}}],
        "invoke-123",
    )
    assert result["content"]["text"] == "result"
    assert captured["method"] == "sampling/createMessage"
    assert captured["params"]["messages"] == [
        {"role": "user", "content": {"type": "text", "text": "draft"}}
    ]
    assert captured["params"]["maxTokens"] == 4096
    assert captured["params"]["includeContext"] == "none"
    assert captured["params"]["systemPrompt"] == "system prompt"
    assert captured["params"]["metadata"] == {"executa_invoke_id": "invoke-123"}
    assert "_clientTimeoutS" not in captured["params"]


def test_concurrent_sampling_responses_are_correlated_by_request_id(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import threading

    plugin._sampling_enabled = True
    captured = []
    captured_lock = threading.Lock()
    both_sent = threading.Event()

    def fake_write(frame):
        with captured_lock:
            captured.append(frame)
            if len(captured) == 2:
                both_sent.set()

    monkeypatch.setattr(plugin, "write_frame", fake_write)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(plugin.sample_message, "system", [{"role": "user", "content": {"type": "text", "text": "first"}}], "invoke-1")
        second = pool.submit(plugin.sample_message, "system", [{"role": "user", "content": {"type": "text", "text": "second"}}], "invoke-2")
        assert both_sent.wait(2), "both reverse requests should be in flight"
        assert len({frame["id"] for frame in captured}) == 2
        for frame in reversed(captured):
            prompt = frame["params"]["messages"][0]["content"]["text"]
            plugin.dispatch_response({
                "jsonrpc": "2.0",
                "id": frame["id"],
                "result": {"content": {"type": "text", "text": f"result-for-{prompt}"}},
            })
        assert first.result(timeout=2)["content"]["text"] == "result-for-first"
        assert second.result(timeout=2)["content"]["text"] == "result-for-second"
