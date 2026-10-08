"""Authoritative invocation identifiers exported to every external adapter.

Runtime sets these after caller-provided environment. Adapters can use them to
label generated data; importers must still validate ownership against artifacts.
"""
EXECUTION_RUN_ID_ENV = "EXECUTION_RUN_ID"
EXECUTION_ATTEMPT_ID_ENV = "EXECUTION_ATTEMPT_ID"
EXECUTION_TASK_ID_ENV = "EXECUTION_TASK_ID"
