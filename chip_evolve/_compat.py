"""Fixed runtime compatibility table; canonical modules own all implementations."""

import importlib
import sys

ALIASES = {
    "artifact_inputs": "chip_evolve.core.artifact_inputs",
    "candidate_facts": "chip_evolve.workflow.candidate_facts",
    "candidates": "chip_evolve.core.candidates",
    "cli": "chip_evolve.workflow.cli",
    "clock": "chip_evolve.core.clock",
    "code_evidence": "chip_evolve.facts.code_evidence",
    "command_requests": "chip_evolve.core.command_requests",
    "commands": "chip_evolve.workflow.commands",
    "comparison_facts": "chip_evolve.core.comparison_facts",
    "config": "chip_evolve.core.config",
    "contracts": "chip_evolve.core.contracts",
    "controller": "chip_evolve.workflow.controller",
    "delivery": "chip_evolve.execution.delivery",
    "design_facts": "chip_evolve.facts.design_facts",
    "diagnosis": "chip_evolve.workflow.diagnosis",
    "dpl": "chip_evolve.workflow.dpl",
    "dpl_case": "chip_evolve.facts.dpl_case",
    "eco": "chip_evolve.workflow.eco",
    "environment": "chip_evolve.workflow.environment",
    "eqy": "chip_evolve.execution.eqy",
    "flow": "chip_evolve.workflow.flow",
    "flow_delivery": "chip_evolve.workflow.flow_delivery",
    "flow_evidence": "chip_evolve.workflow.flow_evidence",
    "flow_recipe": "chip_evolve.facts.flow_recipe",
    "flow_replay": "chip_evolve.workflow.flow_replay",
    "goal": "chip_evolve.workflow.goal",
    "goal_replay": "chip_evolve.workflow.goal_replay",
    "handoff": "chip_evolve.workflow.handoff",
    "handoff_io": "chip_evolve.core.handoff_io",
    "jobs": "chip_evolve.core.jobs",
    "lifecycle": "chip_evolve.core.lifecycle",
    "logic": "chip_evolve.execution.logic",
    "metrics": "chip_evolve.core.metrics",
    "native": "chip_evolve.workflow.native",
    "native_physical": "chip_evolve.execution.native_physical",
    "native_process": "chip_evolve.core.native_process",
    "physical": "chip_evolve.execution.physical",
    "professional": "chip_evolve.workflow.professional",
    "progress": "chip_evolve.core.progress",
    "proof_policy": "chip_evolve.core.proof_policy",
    "recovery": "chip_evolve.workflow.recovery",
    "result_io": "chip_evolve.core.result_io",
    "runtime": "chip_evolve.core.runtime",
    "selection": "chip_evolve.core.selection",
    "source_snapshot": "chip_evolve.facts.source_snapshot",
    "stage_facts": "chip_evolve.facts.stage_facts",
    "validation": "chip_evolve.workflow.validation",
}


def install_aliases():
    package = sys.modules[__package__]
    for name, target in ALIASES.items():
        module = importlib.import_module(target)
        sys.modules[__package__ + "." + name] = module
        setattr(package, name, module)
