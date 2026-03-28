from __future__ import annotations

import json
import unittest
from pathlib import Path

from kagi.compile_result import compile_source_v1
from kagi.diagnostics import DiagnosticError
from kagi.hir import inspect_hir_program_v1
from kagi.subset import run_subset_program, run_subset_program_via_kir


ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "tests" / "golden"
FRONTEND = (ROOT / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
VALID_CASES = [
    "hello",
    "hello_concat",
    "hello_let",
    "hello_print_concat",
    "hello_let_string",
    "hello_let_concat",
    "hello_twice",
    "hello_if",
    "hello_if_stmt",
    "hello_fn",
    "hello_arg_fn",
]


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


class GoldenPipelineTest(unittest.TestCase):
    def test_compile_source_v1_matches_golden_corpus(self):
        for case in VALID_CASES:
            with self.subTest(case=case):
                source = (ROOT / "examples" / f"{case}.ksrc").read_text(encoding="utf-8")
                compiled = compile_source_v1(FRONTEND, source)

                self.assertEqual(json.loads(compiled.parse.raw_ast), read_json(GOLDEN / "parse" / f"{case}.json"))
                self.assertEqual(
                    {
                        "ok": compiled.check.ok,
                        "effects": {
                            "program": compiled.check.effects.program_effects,
                            "functions": compiled.check.effects.function_effects,
                        },
                        "metadata": {
                            "contract_version": compiled.metadata.contract_version,
                            "frontend_entry": compiled.metadata.frontend_entry,
                        },
                        "hir": inspect_hir_program_v1(compiled.lower.hir),
                    },
                    read_json(GOLDEN / "check" / f"{case}.json"),
                )
                self.assertEqual(json.loads(compiled.raw_compile_artifact), read_json(GOLDEN / "lower" / f"{case}.json"))
                self.assertEqual(
                    compiled.stdout,
                    (GOLDEN / "run" / f"{case}.txt").read_text(encoding="utf-8").rstrip("\n"),
                )

    def test_invalid_program_matches_golden_diagnostic(self):
        source = (ROOT / "examples" / "hello_invalid.ksrc").read_text(encoding="utf-8")
        with self.assertRaises(DiagnosticError) as ctx:
            compile_source_v1(FRONTEND, source)
        self.assertEqual(
            ctx.exception.diagnostic.to_json(),
            read_json(GOLDEN / "diagnostics" / "hello_invalid.json"),
        )

    def test_selfhost_pipeline_kir_matches_interpreter_for_golden_corpus(self):
        for case in VALID_CASES:
            with self.subTest(case=case):
                source = (ROOT / "examples" / f"{case}.ksrc").read_text(encoding="utf-8")
                expected = json.loads(run_subset_program(FRONTEND, entry="pipeline", args=[source]))
                actual = json.loads(run_subset_program_via_kir(FRONTEND, entry="pipeline", args=[source]))
                self.assertEqual(actual, expected)
