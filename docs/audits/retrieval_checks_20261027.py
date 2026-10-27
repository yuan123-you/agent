"""Audit entry point; regressions now live in ai-service/tests and must be GREEN.
Run from ai-service: python -m pytest ../docs/audits/retrieval_checks_20261027.py -q
"""
import os
import runpy
import sys
from pathlib import Path

os.environ["LANGFUSE_ENABLED"] = "false"
os.environ["PRODUCT_SYNC_ENABLED"] = "false"
root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "ai-service"))
checks = runpy.run_path(str(root / "ai-service/tests/test_retrieval_regressions.py"))
globals().update({name: value for name, value in checks.items()
                  if name.startswith("test_") or name == "isolated_tool_context"})
