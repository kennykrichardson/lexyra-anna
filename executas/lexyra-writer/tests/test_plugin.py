import json
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lexyra_writer_plugin as plugin


def test_all_styles_are_in_prompt():
    for style in plugin.VALID_STYLES:
        system, messages = plugin.build_messages("Rough words", style)
        assert f"Selected style: {style}." in system
        assert messages[0]["content"]["text"] == "Rough words"
        assert "Never invent or imply a role" in system
        assert "Preserve every factual assertion" in system
        assert "2 years, not 5" in system


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
        lambda system, messages, invoke_id: {"content": {"type": "text", "text": " Draft. "}},
    )
    assert plugin.enhance("Draft", "academic", "invoke-1") == {
        "enhanced_text": "Draft.",
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


MAYA_SOURCE = "On 14 March 2024, Maya Chen led a 3-person team that reduced report errors by 12%; she has 2 years of experience, not 5."
FIDELITY_CASES = [
    (MAYA_SOURCE, "On March 14, 2024, Maya Chen led a three-person team that reduced report errors by 12%; she has two years of experience, not five.", "On March 14, 2024, Maya Chen led a three-person team that reduced report errors by 12%; she has two years of professional experience."),
    ("Ravi did not approve the $4,500 budget on 6 May 2025; he only reviewed it.", "Ravi did not approve the $4,500 budget on May 6, 2025; he only reviewed it.", "Ravi approved the $4,500 budget on May 6, 2025; he reviewed it."),
    ("Leah has some familiarity with Python but has never used it in production; she completed 18 months of coursework only.", "Leah has some familiarity with Python, but has never used it in production; she completed only 18 months of coursework.", "Leah is proficient in Python and has production experience; she completed 18 months of coursework."),
    ("The trial began on 2 February 2023, included 12 participants, and ended after 6 weeks, not 8.", "The trial began on February 2, 2023, included twelve participants, and ended after six weeks rather than eight.", "The trial began on February 2, 2023, included 12 participants, and ended after 8 weeks."),
    ("The contract starts 3 April 2025, not 1 May 2025.", "The contract starts April 3, 2025, not May 1, 2025.", "The contract starts May 3, 2025, not May 1, 2025."),
    ("I supported three launches, excluding Atlas, and did not lead any of them; I contributed as a reviewer only.", "I supported three launches, excluding Atlas, and did not lead any of them; I contributed only as a reviewer.", "I led three launches, including Atlas, and contributed as a reviewer."),
]


@pytest.mark.parametrize("style", list(plugin.VALID_STYLES))
@pytest.mark.parametrize("source,safe,bad", FIDELITY_CASES)
def test_fidelity_regressions_all_styles(style, source, safe, bad, monkeypatch):
    assert plugin.fidelity_issues(source, safe) == []
    assert plugin.fidelity_issues(source, bad), f"checker accepted meaning-changing output for {style}: {source!r}"

    monkeypatch.setattr(plugin, "sample_message", lambda *_: {"content": {"type": "text", "text": bad}})
    result = plugin.enhance(source, style, "invoke-regression")
    assert result["enhanced_text"] == source
    assert result["fidelity_fallback"] is True


MAYA_AUDIT_OUTPUTS = [
    "On March 14, 2024, Maya Chen led a three-person team to achieve a 12% reduction in report errors. Ms. Chen brings two years of professional experience to this role.",
    "On 14 March 2024, Maya Chen directed a three-person team to achieve a 12% reduction in reporting errors. She possesses two years of professional experience, rather than five.",
    "On 14 March 2024, Maya Chen led a 3-person team to reduce report errors by 12%. She has 2 years of experience.",
    "On 14 March 2024, Maya Chen directed a three-person team to achieve a 12% reduction in report errors. She delivers these results with two years of professional experience.",
    "On March 14, 2024, Maya Chen led a three-person team to successfully reduce report errors by 12%. She brings two years of professional experience to this role.",
    "On 14 March 2024, Maya Chen led a three-member team that achieved a 12% reduction in reporting errors. It should be noted that Ms. Chen possesses two years of professional experience, rather than five.",
]


@pytest.mark.parametrize("style,output", list(zip(plugin.VALID_STYLES, MAYA_AUDIT_OUTPUTS)))
def test_exact_prior_live_maya_outputs_fail_closed_for_each_style(style, output, monkeypatch):
    assert plugin.fidelity_issues(MAYA_SOURCE, output)
    monkeypatch.setattr(plugin, "sample_message", lambda *_: {"content": {"type": "text", "text": output}})
    result = plugin.enhance(MAYA_SOURCE, style, "invoke-maya-audit")
    assert result["enhanced_text"] == MAYA_SOURCE
    assert result["fidelity_fallback"] is True
