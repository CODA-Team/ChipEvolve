#!/usr/bin/env python3
"""Compatibility wrapper for the renamed start-seed calibration summarizer."""

from __future__ import annotations

import runpy
from pathlib import Path

runpy.run_path(
    str(Path(__file__).with_name("summarize_start_seed_calibration.py")),
    run_name="__main__",
)
