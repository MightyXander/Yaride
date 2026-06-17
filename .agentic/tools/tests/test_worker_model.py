#!/usr/bin/env python3
"""
test_worker_model.py — закрепление дефолтной модели воркера (Issue #7).

Только stdlib (unittest), без pip-зависимостей:
    python3 -m unittest .agentic/tools/tests/test_worker_model.py
    python3 .agentic/tools/tests/test_worker_model.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent.parent
AGENTIC_ROOT = TOOLS_DIR.parent
EXPECTED_MODEL = "claude-sonnet-4-5"


def _load_launcher():
    spec = importlib.util.spec_from_file_location(
        "worker_launcher", TOOLS_DIR / "worker_launcher.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class WorkerModelDefaultTest(unittest.TestCase):
    def setUp(self) -> None:
        self.launcher = _load_launcher()

    def test_default_constant(self) -> None:
        self.assertEqual(self.launcher.DEFAULT_WORKER_MODEL, EXPECTED_MODEL)

    def test_argparse_default(self) -> None:
        args = self.launcher.build_parser().parse_args(
            ["--issue-id", "7", "--prompt", "x"]
        )
        self.assertEqual(args.model, EXPECTED_MODEL)

    def test_argparse_override(self) -> None:
        args = self.launcher.build_parser().parse_args(
            ["--issue-id", "7", "--prompt", "x", "--model", "claude-opus"]
        )
        self.assertEqual(args.model, "claude-opus")


class WorkerExecScriptTest(unittest.TestCase):
    def test_default_and_flag_present(self) -> None:
        script = (TOOLS_DIR / "wsl_worker_exec.sh").read_text(encoding="utf-8")
        self.assertIn(f'WORKER_MODEL="${{WORKER_MODEL:-{EXPECTED_MODEL}}}"', script)
        self.assertIn('--model "$WORKER_MODEL"', script)

    def test_setup_heredoc_in_sync(self) -> None:
        setup = (TOOLS_DIR / "wsl_setup.py").read_text(encoding="utf-8")
        self.assertIn(f'WORKER_MODEL="${{WORKER_MODEL:-{EXPECTED_MODEL}}}"', setup)
        self.assertIn('--model "$WORKER_MODEL"', setup)


class SessionStateTest(unittest.TestCase):
    def test_state_and_template_have_worker_model(self) -> None:
        for rel in [
            "context/session_state.json",
            "context_templates/session_state.json",
        ]:
            data = json.loads((AGENTIC_ROOT / rel).read_text(encoding="utf-8"))
            self.assertEqual(
                data["orchestrator"].get("worker_model"), EXPECTED_MODEL, rel
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
