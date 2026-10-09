# Durable timing investigation

The original `ask` command remains read-only. `investigate` is an explicit,
budgeted application that can submit supplementary STA through Toolkits and EF.
DF imports the result under a new identity; the investigation resumes on that
identity without changing the baseline. Four installed skills enter the runtime
input and their content hashes are retained in each checkpoint.

```bash
query-agent investigate 'Why did setup get worse?' \
  --snapshot BASELINE_SNAPSHOT --snapshot CANDIDATE_SNAPSHOT \
  --data-url http://127.0.0.1:18924 --kernel-url http://127.0.0.1:18700 \
  --state-root /absolute/path/to/my-investigation --model codex --codex-mode hosted
query-agent state INVESTIGATION_ID --state-root /absolute/path/to/my-investigation
query-agent resume INVESTIGATION_ID --state-root /absolute/path/to/my-investigation \
  --model codex --codex-mode hosted
```

Codex hosted mode uses one subscription session. A Codex agent that is already
the host uses `--model host` and the `act`, `poll`, and `evidence` commands on the
same application instead of launching another model. `--model flash` requires
`--flash-config` and a shared `--cost-ledger`; settings reference a user-only
credential file. Credentials never enter prompts or model traces.

Each checkpoint contains fixed scopes, original skill versions, hypotheses,
counterevidence, saved wire responses, operation receipts, analysis identities,
budget usage and stop reason. Evidence pages retain a digest and continuation;
RFC6901 pointers select existing saved data. A limited preview is not missing
evidence. Partial delivery gets one review when useful budget remains; the agent
may still honestly stop when a required input or permission is unavailable.

`--jev` opts into classification, evidence ranking and support advice. It requires
the configured launcher, price snapshot and shared cost ledger. It does not
authorize execution or prove causality. Low confidence/service failures return
to the main reasoner. Default adoption requires measured whole-task benefit;
classification accuracy alone is insufficient.

`export-handoff` freezes input hashes, facts, unconfirmed hypotheses, evidence,
allowed actions and success criteria. ECO grants come from the operator and are
bound to a snapshot. `receive-handoff` accepts a package hash and permitted
proposal, submits one experiment, evaluates setup/hold in a fresh process, and
imports the result. A later investigation must review the result: execution
success does not mean timing closure. Flow and Code have contracts and rejection
checks; this iteration connects only one real Codex ECO receiver.

The investigation workflow and model adapters are implemented, but their
diagnosis accuracy and advantage over strong reusable scripts are experimental.
Consult the frozen comparison results before treating this build as validated.
