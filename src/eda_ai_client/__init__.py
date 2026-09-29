"""EDA-AI Data Interface client.

    from eda_ai_client import EdaAiClient

    with EdaAiClient(data_url="http://127.0.0.1:8860",
                     kernel_url="http://127.0.0.1:8700") as client:
        for design in client.list_designs():
            print(design["design_id"])
        summary = client.get_stage_summary("ibex-eda_ai_sprint_b1-route")
        print(summary["record_counts"])

The module imports nothing outside the standard library.  See CONTRACT.md for
the tool surface and for what each response field means.
"""

from .client import DEFAULT_DATA_URL, EdaAiClient, EdaAiError
from .schemas import TOOL_NAMES, TOOL_SCHEMAS

__all__ = ["EdaAiClient", "EdaAiError", "DEFAULT_DATA_URL", "TOOL_NAMES", "TOOL_SCHEMAS"]
__version__ = "0.1.0"
