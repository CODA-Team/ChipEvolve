# Tests

Run the deterministic core suite from the project root.

```bash
python3 -m pytest tests/unit
```

`unit/` covers the controller, AST and evaluator with small local fixtures. The ChipEvolve release checkout includes everything this suite needs.

`artifact/` requires the full GoalEvolve research checkout, including the frozen P0 and official AES benchmark. Run `python3 -m pytest tests/artifact` there to check release manifests, the frozen AST graph and the official four-of-four checker. Use the integration campaign to validate a fresh OpenROAD build and a new physical-design run.
