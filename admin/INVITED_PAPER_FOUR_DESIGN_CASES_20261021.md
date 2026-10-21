# Four-design results: editable English paper text

Evidence cut: 2026-10-21T03:53:39.644911+00:00. This is a current review draft; Ibex and Ariane must retain their stated pending status until their actual terminal evidence is available.

## Experiment scope and method

We evaluate ChipEvolve as a local physical-design capability layer consumed by Codex. Codex investigates the design state, selects a professional or an existing native repair action, and decides whether to retain the delivered candidate. Flow, DPL, Goal and ECO keep their original optimization procedures. EF executes tool jobs and manages resources, logs and artifacts; DF and DI provide scoped design facts and evidence references; Query forms the diagnostic context for the next action. The experiments trace actual design-state branches, including rejected outcomes, rather than requiring every professional to improve every design.

Final PPA comes from routed and extracted design states under recorded constraints, libraries and timing conditions. GCD, JPEG and Ibex use ASAP7 FF at 310, 545 and 900 ps, respectively. Ariane uses the provided mapped source, 136 fixed SRAM instances and the original 900 ps constraints; standard cells use FF while the provided SRAM models retain their original corner. Reported power is the common OpenSTA estimate without design-specific SAIF activity. Instance area excludes filler instances and includes SRAM macros when present. WS preserves measured positive slack; canonical WNS is min(0, WS). Setup/hold TNS, electrical and placement violations, native routing counts, core/die geometry and artifact identities remain available in the complete CSV.

## Current reference-to-candidate measurements

| Design | Reference → candidate | Power mW | Power reduction | Instance area µm² | Area reduction | Candidate setup WS ps | Candidate setup TNS ns | Evidence state |
|---|---|---:|---:|---:|---:|---:|---:|---|
| GCD | B0 → G02 | 1.373554 → 0.715649 | 47.898% | 42.6757 → 39.1181 | 8.336% | +0.083406 | 0 | Validated, retained |
| JPEG | JB0 → JP3 | 178.337246 → 152.649298 | 14.404% | 6734.1800 → 6244.1600 | 7.277% | +10.230300 | 0 | Validated, retained |
| IBEX | IB0 → IP3 | 29.243747 → 28.254939 | 3.381% | 2403.7500 → 2342.5800 | 2.545% | +10.149400 | 0 | Measured candidate; validation pending |
| ARIANE | AB0 → original Goal round | 642.415285 → pending | pending | 43672.8 → pending | pending | -285.396000 (reference) | -155.146 (reference) | Original professional round / final delivery pending |

GCD reference-to-final changes include the Flow synthesis/method lineage and the subsequent optimization relay. The within-relay gains below use the actual physical parent. Reference-to-final reductions and within-parent improvements answer different questions; neither comparison isolates every component of the complete platform.

## GCD: two positive professional relays

Flow candidate F37 measures 0.890911557 mW and 44.8918 µm² but exceeds the original 42.6757 µm² area bound. Query passes the measured state and diagnostic context to Goal. G02 reaches 0.715648639 mW and 39.1181 µm², reducing power by 19.672% and area by 12.861% relative to F37 while closing setup and hold timing. A second branch consumes the saved Flow placement checkpoint with DPL. DPL Student01 improves native HPWL to 530.9 µm, but its completed state exceeds the area bound. Goal continues this actual DPL state and produces DG1 at 0.819291221 mW and 39.6139 µm², reducing power by 12.610% and area by 11.929% relative to the DPL parent. Both final branches pass all 18-output sequential equivalence and an independent complete routing/extraction replay with seven exactly matching recorded values. Codex retains lower-power G02.

ECO operates on the timing-failing G03 branch, where its eight-round native session reduces the magnitude of setup TNS by 69.073%. A separately recorded routing-completion step removes the remaining native routing violations, but setup TNS remains −0.266838 ns. This branch is rejected. The case therefore demonstrates four actual professional participants, two validated positive relays and a genuine unsuccessful ECO branch. It does not require a successful serial traversal of all four professionals.

## JPEG: timing recovery from a professional checkpoint

Goal03 provides the actual physical parent for the JPEG continuation. Earlier ECO attempts and routing-delivery failures remain in the trace. Query exposes the timing and delivery state, and Codex requests an existing native VT/sizing repair with a declared 30 ps internal margin, followed by complete routing and extraction. JP3 measures 152.64929831 mW and 6244.16 µm², with setup WS +10.2303 ps, hold WS +12.5118 ps, zero setup/hold TNS and zero electrical, placement and native routing violations. Relative to the ORFS reference, power and area decrease by 14.404% and 7.277%. Relative to the infeasible Goal03 parent, power increases by 1.181% to restore timing feasibility. All 27 outputs / 7082 EQY partitions pass sequential equivalence, and the independent recorded-delivery replay reproduces all seven values exactly. Public DF/DI identities and the actual retained pointer are verified.

This result is a physical-state relay from Goal to a Codex-directed native repair. It is not reported as a successful ECO session or a composition of the earlier Student C++ implementations. The unsuccessful ECO branches remain visible.

## Ibex: the same action class on another design

The original Goal round and its four Students complete, but the common final measurements violate setup or electrical limits. Subsequent timing-only and post-route attempts are recorded separately. Query on the actual IP2 state motivates a VT/sizing action with a 30 ps internal margin and slew repair before and after timing repair. IP3 is physically feasible at 28.254939243 mW and 2342.58 µm², with setup WS +10.1494 ps, hold WS +27.7278 ps and zero setup/hold TNS, electrical, placement and native routing violations. Its measured power and area are 3.381% and 2.545% below the ORFS reference. The design retains its original 900 ps clock and final constraints.

The exact final 106-output functional proof and independent delivery replay are not yet complete, so IP3 is reported as a physically feasible candidate, not a validated retained result. IB0 remains the incumbent. Qualified native EQY continuation preserves the same model and all 2046 obligations while allowing the original Ariane work to use the shared machine.

## Ariane: current professional run, pending final outcome

The mapped Ariane reference completes physical routing and final fact publication at 642.41528511 mW and 43672.8 µm², with setup WS −285.396 ps, setup TNS −155.146 ns and 436 slew violations. It is an infeasible physical reference, not a validated final solution. Query identifies a deep register-to-output logic path and supplies that context to the original Goal timing-focused round. A verified handoff defect that dropped inherited baseline DRV observations was corrected before the independent current round. Its actual Parent receives DRV 294 and runtime 739, with the original three-objective contract unchanged.

The current one-round/four-Student process has three successful initial native evaluations and one native timeout. The first native constraint-repair evaluations for Student01 and Student04 also complete successfully; immutable public EF archives preserve their post-route database and netlist hashes. These are native-stage outcomes. Teacher selection, common final physical delivery and the final business decision remain pending. No final PPA gain is assigned to this ongoing round.

## Platform execution and evidence

The operation trace covers design-status inspection, Query diagnosis, professional dispatch, EF job execution, artifact registration, DF/DI fact publication and the next Codex decision. Every new EDA, build and proof job in the reported branches is submitted through EF. Physical handoffs record design identity, actual parent, checkpoint hashes, constraints, tool/source identity and Query context. They also state which stages must be rebuilt: a placement-stage handoff cannot preserve a later routed result by implication. Final business acceptance is separate from each professional’s internal selection.

Execution admission and design facts remain shared across professionals. A real memory-contention event is resolved by saving completed proof partitions, freeing the public EF reservation for the existing Ariane build and full routing, then continuing the unchanged proof with native EQY support. This operation changes scheduling, not the optimization objective or proof scope.

Costs are reported with their measured scope. Saved EF sampled CPU and native model input/output/cache receipts cover the listed tasks and calls; they do not include all parent Codex reasoning or service overhead. The current operation records demonstrate the interface and handoff work performed by the platform. They do not establish a token or wall-clock savings ratio without a matching direct task.

## Paper figures and evidence

- GCD: `gcd-measured-relay-r4.pdf` and `gcd-ppa-observations-r2.pdf`.
- JPEG: `jpeg-measured-relay-r9.pdf`.
- Ibex: `ibex-measured-relay-r7.pdf`; Ariane: `ariane-measured-relay-r10.pdf` (pending steps explicitly labelled).
- Complete measurements: [CSV](INVITED_PAPER_METRICS_20261020.csv).
- Full GCD narrative and the existing same-recipe development control: [GCD case](INVITED_PAPER_GCD_CASE_TEXT_20261020.md).
- Shared execution and fact interfaces: [platform operation trace](A29_PLATFORM_OPERATION_TRACE_20261020.md).
- DPLEvolve/ReviewDSE is one source-optimization project. GoalEvolve is separate; TimingECOAgent retains its original external research attribution.
