# Agent dispatch

Consult this table when calling ChipEvolve as the Control Agent. First use
`chip-evolve.py --config CONFIG diagnose --result RESULT` to obtain cited facts
and a professional context. Pass the selected agent an explicit source result,
objective, context, and time budget. Choose the narrowest change that the
evidence supports.

| Agent and entry | Choose it when | Required input and permitted change | Check the return |
| --- | --- | --- | --- |
| [Query Agent](query-agent/docs/investigation.md), `diagnose` | A baseline or comparison needs evidence about timing, power, area, or a failed run. | Registered result and its snapshots. It can query through the SDK and request bounded analyses within its configured permissions. The result separates facts, hypotheses, and evidence gaps. | Check the design, run, snapshots, citations, and any remaining gaps. |
| [Flow Agent](flow-agent/RUNNING.md), `run --capability flow` | The evidence points to a change in the ORFS recipe, stage settings, or optimization parameters. | A reference result with its ORFS recipe and stage artifacts. The deployment binds the Flow source, interpreter, and tool profile. Changes are to flow parameters and constraints within the authorized objective. | Compare routed candidates against the frozen reference. Keep the stage execution record and any candidate rejections. |
| [DPLEvolve](dplevolve/AGENTS.md), `run --capability dpl` | Detailed placement, legalization, or refinement is the mechanism to change. | The source run's pre-CTS placement inputs, a DPL case, seed source, and compatible OpenROAD core. The controller prepares each private Student source from the Teacher assignment. Each Student edits the detailed-placement C++ extension and uses the generated trial helpers to build and evaluate through EF. | Verify that CTS and routing used the returned placement, then compare the final metrics. |
| [GoalEvolve](goalevolve/README.md#chipevolve-local-integration), `run --capability goal` | The diagnosed timing, power, or area problem calls for changing an OpenROAD optimization algorithm. | A registered design checkpoint, a compatible OpenROAD source seed, the benchmark and checker inputs, matching technology data, and a campaign profile. Its Teacher/Student loop edits bounded OpenROAD C++ mechanisms. | Check the native validity results and identify the source and binary that produced the candidate. Compare the routed and measured result against the objective. |
| [TimingECOAgent](timing-eco-agent/PLATFORM.md), `run --capability eco` | Post-route evidence supports a local timing repair with an available ECO operation. | Registered routed ODB, SDC, and SPEF, matching libraries, and a native ECO binding. Edits use the permitted local ECO operations. | Inspect the original and returned setup/hold metrics, electrical checks, and route validity. The best checkpoint can be the input. |

For a source run that already meets the objective, keep the reference unless a
specific improvement is supported. If the required input, proof, or deployment
binding is missing, use the missing item to explain why the agent cannot be
dispatched. If a job failed before producing a result, use `status` or `watch`
to inspect its Execution Foundation run and artifacts. `orfs` is the baseline
and physical execution capability.

```bash
python3 chip-evolve.py --config CONFIG run --design DESIGN \
  --capability CAPABILITY --key KEY --source RESULT --context CONTEXT \
  --seconds SECONDS
```

The command uses the source result's objective by default. Pass `--objective`
to supply an explicit objective with matching measurement conditions. Use
`--rounds` for search and `--candidates` for Flow and DPL. Use
`--flow-recipe source` to reconstruct the registered ORFS recipe when the
source contains that recipe. The launcher checks the context's design, run,
and snapshot and verifies the objective's measurement conditions.

Each module maintains its own runtime instructions and controller. Its
`AGENTS.md` guides work on its source code.

| Agent | Runtime instructions | Controller |
| --- | --- | --- |
| Query | [Investigation skills](query-agent/src/query_agent/skills) and [prompts](query-agent/src/query_agent/prompts) | [Investigation workflow](query-agent/docs/investigation.md) |
| Flow | [Prompts](flow-agent/flow/prompts.py) and [model settings](flow-agent/flow/drp_config.json) | [Native driver](flow-agent/flow/maindriver.sh) |
| DPL | [Teacher and Student templates](dplevolve/prompt_templates/teacher_loop) | [Platform workflow](dplevolve/scripts/platform) |
| Goal | [Teacher](goalevolve/goalevolve/agents/teacher.py) and [Student](goalevolve/goalevolve/agents/codex_student.py) | [Native CLI](goalevolve/goalevolve/cli.py) |
| ECO | [Expert instructions](timing-eco-agent/prompts/AGENTS.md) | [Native controller](timing-eco-agent/src/main_orch.py) |

For release readiness and the difference between a native replay and a full
search, see [the engineering status](../TASKS.md).
