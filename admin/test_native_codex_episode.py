"""Native episode receipts preserve real failure, usage and input identity."""

import json
import sys
from pathlib import Path

import pytest

from admin.run_native_codex_episode import main, run, summarize
from chip_evolve.config import read, write
from chip_evolve.jobs import digest


def events(path, values):
    path.write_text("\n".join(json.dumps(v) for v in values) + "\n")


def usage(inputs=100, cached=60, outputs=5):
    return {
        "type": "turn.completed",
        "usage": {
            "input_tokens": inputs,
            "cached_input_tokens": cached,
            "output_tokens": outputs,
            "reasoning_output_tokens": 3,
        },
    }


def test_multiple_turns_sum_actual_input_and_output_without_cache_double_count(
    tmp_path,
):
    path = tmp_path / "events.jsonl"
    events(
        path,
        [
            {"type": "turn.started"},
            usage(),
            {"type": "turn.started"},
            usage(80, 70, 9),
        ],
    )
    result = summarize(path)
    assert result["usage_complete"]
    assert result["usage"] == {
        "input_tokens": 180,
        "cached_input_tokens": 130,
        "output_tokens": 14,
    }
    assert result["input_plus_output_tokens"] == 194


@pytest.mark.parametrize(
    "tail",
    [
        [{"type": "turn.started"}],
        [{"type": "turn.failed", "error": {"message": "interrupted"}}],
        [{"type": "turn.started"}, {"type": "turn.completed"}],
        [{"type": "turn.started"}, usage(cached=101)],
    ],
)
def test_unknown_interrupted_or_invalid_usage_is_not_zero(tmp_path, tail):
    path = tmp_path / "events.jsonl"
    events(path, [{"type": "turn.started"}, usage(), *tail])
    result = summarize(path)
    assert not result["usage_complete"] and result["usage"] is None
    assert result["input_plus_output_tokens"] is None
    assert result["known_usage_lower_bound"]["input_tokens"] == 100


def test_malformed_json_kept_as_a_trace_problem(tmp_path):
    path = tmp_path / "events.jsonl"
    events(path, [{"type": "turn.started"}, usage()])
    with path.open("a") as stream:
        stream.write('{"type":\n')
    result = summarize(path)
    assert not result["usage_complete"] and result["trace_problems"][0]["line"] == 3


def episode(tmp_path, body="", seconds: float = 5):
    prompt, schema, native = [
        tmp_path / n for n in ("prompt.txt", "schema.json", "native.py")
    ]
    prompt.write_text("Read real inputs and return the observed fact.\n")
    write(schema, {"type": "object"})
    native.write_text(
        "import sys,json,time\nfrom pathlib import Path\n"
        + "prompt=sys.stdin.read()\n"
        + 'print(json.dumps({"type":"turn.started"}),flush=True)\n'
        + body
        + "\nanswer=Path(sys.argv[sys.argv.index('--output-last-message')+1])\n"
        + 'answer.write_text(json.dumps({"prompt":prompt,"arguments":sys.argv[1:]}))\n'
        + f"print(json.dumps({usage()!r}),flush=True)\n"
        + "print('transport note on stderr',file=sys.stderr)\n"
    )
    spec = tmp_path / "episode.json"
    write(
        spec,
        {
            "schema": "chip-evolve.native-codex-episode.v1",
            "native_command": [sys.executable, str(native)],
            "prompt": str(prompt),
            "answer_schema": str(schema),
            "input_hashes": {
                str(p): digest(p)
                for p in [Path(sys.executable), native, prompt, schema]
            },
            "wall_seconds": seconds,
            "model": "gpt-6.1-sol",
            "reasoning_effort": "medium",
        },
    )
    return spec, tmp_path / "attempt"


def test_native_stdin_eof_separate_streams_and_no_repeat_attempt(tmp_path):
    spec, output = episode(tmp_path)
    result = run(spec, output)
    assert result["status"] == "native_completed"
    assert result["answer"]["prompt"] == Path(read(spec)["prompt"]).read_text()
    args = result["answer"]["arguments"]
    assert args[-1] == "-" and "gpt-6.1-sol" in args
    assert "workspace-write" in args and "--ignore-user-config" in args
    assert "transport note" in (output / "stderr.txt").read_text()
    assert "transport note" not in (output / "events.jsonl").read_text()
    assert result["business_correctness"] == "requires_independent_verification"
    assert not result["token_hard_limit_enforced"]
    original = digest(output / "receipt.json")
    with pytest.raises(FileExistsError):
        run(spec, output)
    assert digest(output / "receipt.json") == original


def test_mutated_pinned_input_rejected_before_native_invocation(tmp_path):
    spec, output = episode(tmp_path)
    Path(read(spec)["prompt"]).write_text("changed")
    with pytest.raises(ValueError, match="Pinned episode inputs changed"):
        run(spec, output)
    assert not output.exists()


def test_explicit_common_account_profile_is_recorded_without_fallback(tmp_path):
    spec, output = episode(tmp_path)
    value = read(spec)
    value["sandbox"] = "danger-full-access"
    write(spec, value)
    result = run(spec, output)
    assert result["sandbox"] == "danger-full-access"
    assert "danger-full-access" in result["answer"]["arguments"]


def test_unknown_profile_does_not_start_a_native_process(tmp_path):
    spec, output = episode(tmp_path)
    value = read(spec)
    value["sandbox"] = "unqualified"
    write(spec, value)
    with pytest.raises(ValueError, match="Unqualified native sandbox"):
        run(spec, output)
    assert not output.exists()


def test_native_changes_to_input_are_a_failed_attempt(tmp_path):
    prompt = tmp_path / "prompt.txt"
    spec, output = episode(tmp_path, f"Path({str(prompt)!r}).write_text('changed')\n")
    result = run(spec, output)
    assert result["status"] == "failed" and result["changed_inputs"] == [str(prompt)]
    assert result["usage_complete"]


def test_timeout_retains_trace_and_does_not_invent_missing_usage(tmp_path):
    spec, output = episode(tmp_path, "time.sleep(30)\n", seconds=0.5)
    result = run(spec, output)
    assert result["status"] == "timed_out"
    assert result["cleanup"]["status"] == "completed"
    assert result["usage"] is None and not result["usage_complete"]
    assert result["exit_code"] != 0
    assert (output / "events.jsonl").read_text()


def test_cli_prints_compact_receipt_without_repeating_native_command_output(
    tmp_path, monkeypatch, capsys
):
    event = {
        "type": "item.completed",
        "item": {
            "type": "command_execution",
            "command": "native fact read",
            "aggregated_output": "VERY_LARGE_TRACE_PAYLOAD",
            "exit_code": 0,
        },
    }
    spec, output = episode(tmp_path, f"print(json.dumps({event!r}),flush=True)\n")
    monkeypatch.setattr(
        sys, "argv", ["episode", "--spec", str(spec), "--output", str(output)]
    )
    with pytest.raises(SystemExit) as caught:
        main()
    assert caught.value.code == 0
    text = capsys.readouterr().out
    summary = json.loads(text)
    assert summary["status"] == "native_completed"
    assert "VERY_LARGE_TRACE_PAYLOAD" not in text
    assert read(summary["receipt"])["commands"][0]["aggregated_output"] == (
        "VERY_LARGE_TRACE_PAYLOAD"
    )
