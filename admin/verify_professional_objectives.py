"""Real model-transport checks; no EDA search or professional scoring is changed."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

from run_dplevolve_native import write_json

ROOT = Path(__file__).resolve().parents[1]


def verify(state: Path, agent: str) -> dict:
    objective = state / "fix-a2-a3/shared-objective.json"
    output = state / "fix-a2-a3/model-checks" / agent
    output.mkdir(parents=True, exist_ok=False)
    prompt = (
        "Use no tools. This is only a shared-objective delivery check, not an "
        "optimization experiment. From the platform_shared_objective supplied "
        "with this request, return a JSON object with objective_id, design_id, "
        "clock_period_ns, power_total_w_max, core_area_um2_max and die_area_um2_max. "
        "Copy values exactly. Do not change professional scoring or run EDA."
    )
    environment = dict(os.environ, EDA_PLATFORM_OBJECTIVE=str(objective))
    python = ROOT / (agent + "/.venv/bin/python")
    model = "gpt-6.1-sol"
    if agent == "flow-agent":
        ledger = output / "usage.jsonl"
        ledger.touch()
        profile = output / "profile.json"
        write_json(profile, {"state_root": str(output)})
        environment.update(
            DRP_EXECUTION_BACKEND="platform",
            DRP_CAMPAIGN_ID="a3-objective-check",
            DRP_ITER="1",
            DRP_LLM_USAGE_FILE=str(ledger),
            DRP_PLATFORM_CONFIG=str(profile),
            DRP_CODEX_AUDIT_DIR=str(output / "codex-audit"),
        )
        code = (
            "import os,json;from pathlib import Path;"
            "from llm_client import CodexClient;from platform_model import tracked_completion;"
            "r=tracked_completion(CodexClient({'timeout':180}),"
            + repr({"model": model, "messages": [{"role": "user", "content": prompt}]})
            + ",{'stage':'objective-check','operation':'read-constraints'});"
            + "Path("
            + repr(str(output / "reply.txt"))
            + ").write_text(r.choices[0].message.content)"
        )
        cwd = ROOT / "flow-agent/flow"
    elif agent == "dplevolve":
        native_profile = state / "agents/dpl/profile.json"
        native = json.loads(native_profile.read_text())
        environment.update(
            DPL_EVOLVE_PLATFORM_PROFILE=str(native_profile),
            DPL_EVOLVE_AGENT_ROOT=str(ROOT / agent),
            DPL_EVOLVE_STATE_ROOT=str(output),
            ORFS_ROOT=native["orfs_root"],
            CODEX_HOME=str(Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()),
        )
        settings = {
            "model_provider": "chatgpt-http",
            "model_providers.chatgpt-http.name": "ChatGPT HTTP",
            "model_providers.chatgpt-http.base_url": "https://chatgpt.com/backend-api/codex",
            "model_providers.chatgpt-http.wire_api": "responses",
            "model_providers.chatgpt-http.requires_openai_auth": True,
            "model_reasoning_effort": "low",
            "web_search": "disabled",
        }
        args = [
            "--operation-id",
            "objective-check",
            "--operations-dir",
            str(output / "operations"),
            "--prompt",
            prompt,
            "--model",
            model,
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
            "--cwd",
            str(output),
            "--auto-resume-max-attempts",
            "0",
        ]
        for name, value in settings.items():
            args.extend(["--config", name + "=" + json.dumps(value)])
        code = (
            "from scripts.codex_exec.runner import main;raise SystemExit(main("
            + repr(args)
            + "))"
        )
        cwd = ROOT / agent
    elif agent == "goalevolve":
        python = state / "fix-a2-a3/goal-env/bin/python"
        profile = output / "profile.json"
        write_json(
            profile,
            {
                "codex": {
                    "auth_mode": "existing_codex",
                    "home": str(
                        Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()
                    ),
                }
            },
        )
        environment["GOALEVOLVE_PLATFORM_PROFILE"] = str(profile)
        code = (
            "from pathlib import Path;from goalevolve.agents.codex_runtime import CodexRuntimeConfig,PersistentCodexRunner;"
            + "r=PersistentCodexRunner(CodexRuntimeConfig(model="
            + repr(model)
            + ",reasoning_effort='low',retries=1,timeout_s=180)).run("
            + "state_root=Path("
            + repr(str(output))
            + "),identity='teacher',operation_id='round_01',cwd=Path("
            + repr(str(output))
            + "),artifact_root=Path("
            + repr(str(output / "turn"))
            + "),prompt="
            + repr(prompt)
            + ");raise SystemExit(0 if r.ok else 1)"
        )
        cwd = ROOT / agent
    else:
        cwd = output / "source/src"
        cwd.mkdir(parents=True)
        shutil.copyfile(
            ROOT / agent / "src/platform_codex.py", cwd / "platform_codex.py"
        )
        environment.update(TIMINGECO_EF_LEAF="1", TIMINGECO_CODEX_TIMEOUT="180")
        code = (
            "from pathlib import Path;from platform_codex import call_codex;r,_=call_codex('Preserve native ECO strategy and scoring.',"
            + repr(prompt)
            + ");Path("
            + repr(str(output / "reply.txt"))
            + ").write_text(r)"
        )
    with (output / "driver.log").open("w") as log:
        result = subprocess.run(
            [str(python), "-c", code],
            cwd=cwd,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=240,
            check=False,
        )
    if result.returncode:
        raise RuntimeError("Model transport check failed: " + str(output))
    reply_path = (
        output / "operations/objective-check/codex_last_message.txt"
        if agent == "dplevolve"
        else output / "turn/last_message.md"
        if agent == "goalevolve"
        else output / "reply.txt"
    )
    text = reply_path.read_text().strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    # ECO retains its native Analysis/Tcl envelope around the JSON fact block.
    actual, _ = json.JSONDecoder().raw_decode(text[text.index("{") :])
    value = json.loads(objective.read_text())
    expected = {
        "objective_id": value["objective_id"],
        "design_id": value["design_id"],
        "clock_period_ns": value["conditions"]["clock_period_ns"],
        **{
            key: value["constraints"][key]
            for key in ("power_total_w_max", "core_area_um2_max", "die_area_um2_max")
        },
    }
    if actual != expected:
        raise ValueError("Professional model did not receive the same shared objective")
    receipt = {
        "agent": agent,
        "received": actual,
        "delivery_verified": True,
        "scope": "model transport only; not a new search round",
    }
    write_json(output / "acceptance.json", receipt)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument(
        "--agent",
        choices=["flow-agent", "dplevolve", "goalevolve", "timing-eco-agent"],
        required=True,
    )
    args = parser.parse_args()
    print(json.dumps(verify(args.state.resolve(), args.agent)))
