# CPU LEGALM Reference Request

This directory is a handoff packet for someone implementing a high-performance
CPU LEGALM-style detailed-placement legalizer.

It is **not** a plugin ABI and not an integration contract.  The goal is to
give an external implementer enough clean data structures and algorithmic
constraints to build a strong standalone reference implementation.  We can
later study or port the best ideas into `detailed_placement_evolve`.

Files:

- `DATA_MODEL.md`: the input/output structures and invariants the algorithm
  should assume.
- `IMPLEMENTATION_PROMPT.md`: a ready-to-send prompt for the external coding or
  research agent.

Expected implementation style:

- standalone C++17 or newer CPU implementation,
- deterministic when requested,
- no OpenROAD object dependency,
- no GPU dependency,
- scalable to JPEG and larger cases,
- rich runtime/quality telemetry.
