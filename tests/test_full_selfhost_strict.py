from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from kagi.compile_result import compile_source_v1
from kagi.diagnostics import DiagnosticError
from kagi.selfhost_runtime import (
    build_selfhost_frontend_v1,
    compile_selfhost_frontend_to_kir_v1,
    execute_selfhost_frontend_entry_v1,
)


class FullSelfhostStrictTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]
        cls.frontend_source = (cls.root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        cls.frontend_kir = (cls.root / "examples" / "selfhost_frontend.kir.json").read_text(encoding="utf-8")
        cls.hello_arg_fn = (cls.root / "examples" / "hello_arg_fn.ksrc").read_text(encoding="utf-8")

    def test_build_selfhost_frontend_reaches_fixed_point(self):
        build = build_selfhost_frontend_v1(self.frontend_source)
        self.assertTrue(build.fixed_point)
        self.assertEqual(build.stage1_kir, build.stage2_kir)
        self.assertEqual(build.stage1_kir, self.frontend_kir)

    def test_freeze_from_kir_is_identity_at_fixed_point(self):
        stage1 = compile_selfhost_frontend_to_kir_v1(self.frontend_source)
        stage2 = compile_selfhost_frontend_to_kir_v1(stage1)
        self.assertEqual(stage1, self.frontend_kir)
        self.assertEqual(stage2, stage1)

    def test_mainline_self_build_does_not_import_host_parser_or_lowerer(self):
        watched = [
            "kagi.subset_parser",
            "kagi.subset_lexer",
            "kagi.lower_subset_to_kir",
        ]
        for name in watched:
            sys.modules.pop(name, None)

        with patch("kagi.selfhost_runtime.execute_subset_entry_via_kir_v0", side_effect=AssertionError("legacy subset fallback should not be used")):
            with patch("kagi.selfhost_runtime.parse_subset_program", side_effect=AssertionError("subset parser should not be used")):
                with patch("kagi.selfhost_runtime.lower_subset_program_to_kir_v0", side_effect=AssertionError("subset lowering should not be used")):
                    build = build_selfhost_frontend_v1(self.frontend_source)

        self.assertTrue(build.fixed_point)
        for name in watched:
            self.assertNotIn(name, sys.modules, name)

    def test_compile_source_v1_still_works_after_self_build(self):
        build = build_selfhost_frontend_v1(self.frontend_source)
        compiled = compile_source_v1(self.frontend_source, self.hello_arg_fn)
        self.assertTrue(build.fixed_point)
        self.assertEqual(compiled.stdout, "hello, world!")

    def test_execute_selfhost_pipeline_from_kir_image(self):
        value = execute_selfhost_frontend_entry_v1(self.frontend_kir, entry="pipeline", args=[self.hello_arg_fn])
        self.assertIsInstance(value, str)
        self.assertIn('"kind":"pipeline_bundle"', value)

    def test_cli_selfhost_build_reports_fixed_point(self):
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "kagi.cli",
                "selfhost-build",
                "--json",
                str(self.root / "examples" / "selfhost_frontend.ks"),
            ],
            cwd=self.root,
            env={"PYTHONPATH": str(self.root / "src")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["fixed_point"])
        self.assertEqual(payload["stage1_kir"], json.loads(self.frontend_kir))
        self.assertEqual(payload["stage2_kir"], json.loads(self.frontend_kir))

    def test_noncanonical_frontend_is_rejected(self):
        with self.assertRaises(DiagnosticError) as ctx:
            build_selfhost_frontend_v1("fn pipeline(source) { return source; }")
        self.assertEqual(ctx.exception.diagnostic.message, "error: unsupported source")


if __name__ == "__main__":
    unittest.main()
