import json
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import Mock, patch

from kagi.artifact import PrintArtifactV1
from kagi.bootstrap_builders import builtin_hir_to_analysis, builtin_hir_to_kir, builtin_program_ast_to_hir
from kagi.compile_result import compile_source_v1
from kagi.hir import lower_surface_program_to_hir_v1
from kagi.kir import KIRPrintV0, KIRProgramV0, KIRStringV0, serialize_kir_program_v0
from kagi.selfhost_analysis import SelfhostAnalysisV1
from kagi.selfhost_bundle import parse_selfhost_pipeline_bundle_v1, selfhost_pipeline_bundle_v1_to_json
import kagi.selfhost_runtime as selfhost_runtime
from kagi.surface_ast import parse_surface_program_v1


class BundleKirFutureTest(unittest.TestCase):
    def test_compile_source_v1_prefers_bundle_kir_over_python_hir_lowering(self):
        frontend_source = "fn pipeline(source) { return source; }"
        surface_ast = parse_surface_program_v1(
            '{"kind":"program","functions":[],"statements":[{"kind":"print","expr":{"kind":"string","value":"hello"}}]}'
        )
        hir = lower_surface_program_to_hir_v1(surface_ast)
        kir = KIRProgramV0(instructions=[KIRPrintV0(expr=KIRStringV0(value="hello"))])
        bundle = SimpleNamespace(
            raw_ast='{"kind":"program","functions":[],"statements":[{"kind":"print","expr":{"kind":"string","value":"hello"}}]}',
            raw_hir='{"kind":"hir_program","functions":[],"statements":[{"kind":"print","expr":{"kind":"string","value":"hello"}}]}',
            raw_analysis='{"kind":"analysis_v1","function_arities":{},"effects":{"program":["print"],"functions":{}}}',
            raw_check="ok",
            raw_artifact='{"kind":"print_many","texts":["hello"]}',
            raw_compile='{"kind":"print_many","texts":["hello"]}',
            surface_ast=surface_ast,
            hir=hir,
            kir=kir,
            analysis=SelfhostAnalysisV1(function_arities={}, program_effects=["print"], function_effects={}),
            artifact=PrintArtifactV1(texts=["hello"]),
            compile_artifact=PrintArtifactV1(texts=["hello"]),
        )

        with patch("kagi.compile_result.execute_selfhost_frontend_entry_v1", return_value="bundle"):
            with patch("kagi.compile_result.parse_selfhost_pipeline_bundle_v1", return_value=bundle):
                compiled = compile_source_v1(frontend_source, "ignored source")

        self.assertEqual(compiled.lower.kir, kir)
        self.assertEqual(compiled.compile_kir, kir)

    def test_compile_source_v1_canonical_frontend_does_not_call_python_bootstrap_builtins(self):
        root = Path(__file__).resolve().parents[1]
        frontend_source = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        corpus = [
            "hello.ksrc",
            "hello_concat.ksrc",
            "hello_let.ksrc",
            "hello_if.ksrc",
            "hello_fn.ksrc",
            "hello_arg_fn.ksrc",
        ]

        for name in corpus:
            with self.subTest(case=name):
                source = (root / "examples" / name).read_text(encoding="utf-8")
                ast_spy = Mock(side_effect=builtin_program_ast_to_hir)
                kir_spy = Mock(side_effect=builtin_hir_to_kir)
                analysis_spy = Mock(side_effect=builtin_hir_to_analysis)
                with patch.object(
                    selfhost_runtime,
                    "SUBSET_KIR_BUILTINS",
                    {
                        **selfhost_runtime.SUBSET_KIR_BUILTINS,
                        "program_ast_to_hir": ast_spy,
                        "hir_to_kir": kir_spy,
                        "hir_to_analysis": analysis_spy,
                    },
                ):
                    compiled = compile_source_v1(frontend_source, source)

                self.assertEqual(ast_spy.call_count, 0)
                self.assertEqual(kir_spy.call_count, 0)
                self.assertEqual(analysis_spy.call_count, 0)
                self.assertEqual(compiled.stdout, "hello, world!")

    def test_compile_source_v1_canonical_frontend_examples_do_not_call_python_bootstrap_builders(self):
        root = Path(__file__).resolve().parents[1]
        frontend_source = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        cases = {
            "hello.ksrc": "hello, world!",
            "hello_print_concat.ksrc": "hello, world!",
            "hello_let_string.ksrc": "hello, world!",
            "hello_let_concat.ksrc": "hello, world!",
            "hello_twice.ksrc": "hello\nworld",
            "hello_fn.ksrc": "hello, world!",
            "hello_arg_fn.ksrc": "hello, world!",
            "hello_if.ksrc": "hello, world!",
            "hello_if_stmt.ksrc": "hello, world!",
        }
        forbidden_builder_names = (
            "print_ast",
            "program_ast",
            "program_if_expr_print_ast",
            "program_if_stmt_ast",
            "program_print_concat_ast",
            "program_let_concat_print_ast",
            "program_single_arg_fn_call_ast",
            "program_let_print_ast",
            "program_two_prints_ast",
            "program_text",
            "program_zero_arg_fn_call_ast",
            "program_ast_to_hir",
            "hir_to_kir",
            "hir_to_analysis",
        )
        forbidden_builtins = {
            name: Mock(side_effect=AssertionError(f"{name} should not be used by canonical bundle path"))
            for name in forbidden_builder_names
        }

        with patch.object(
            selfhost_runtime,
            "SUBSET_KIR_BUILTINS",
            {
                **selfhost_runtime.SUBSET_KIR_BUILTINS,
                **forbidden_builtins,
            },
        ):
            for filename, expected_stdout in cases.items():
                with self.subTest(case=filename):
                    source = (root / "examples" / filename).read_text(encoding="utf-8")
                    compiled = compile_source_v1(frontend_source, source)
                    self.assertEqual(compiled.stdout, expected_stdout)

        for name, spy in forbidden_builtins.items():
            self.assertEqual(spy.call_count, 0, name)

    def test_canonical_frontend_entries_do_not_call_python_bootstrap_builtins(self):
        root = Path(__file__).resolve().parents[1]
        frontend_source = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        cases = {
            "hello.ksrc": ("hir", "kir", "analysis"),
            "hello_if.ksrc": ("hir", "kir", "analysis"),
            "hello_fn.ksrc": ("hir", "kir", "analysis"),
            "hello_arg_fn.ksrc": ("hir", "kir", "analysis"),
        }

        for filename, entries in cases.items():
            for entry in entries:
                with self.subTest(case=filename, entry=entry):
                    source = (root / "examples" / filename).read_text(encoding="utf-8")
                    ast_spy = Mock(side_effect=builtin_program_ast_to_hir)
                    kir_spy = Mock(side_effect=builtin_hir_to_kir)
                    analysis_spy = Mock(side_effect=builtin_hir_to_analysis)
                    with patch.object(
                        selfhost_runtime,
                        "SUBSET_KIR_BUILTINS",
                        {
                            **selfhost_runtime.SUBSET_KIR_BUILTINS,
                            "program_ast_to_hir": ast_spy,
                            "hir_to_kir": kir_spy,
                            "hir_to_analysis": analysis_spy,
                        },
                    ):
                        value = selfhost_runtime.execute_selfhost_frontend_entry_v1(
                            frontend_source,
                            entry=entry,
                            args=[source],
                        )

                    self.assertIsInstance(value, str)
                    self.assertFalse(value.startswith("error:"))
                    self.assertEqual(ast_spy.call_count, 0)
                    self.assertEqual(kir_spy.call_count, 0)
                    self.assertEqual(analysis_spy.call_count, 0)

    def test_parse_selfhost_pipeline_bundle_v1_future_kir_field_roundtrips(self):
        kir = KIRProgramV0(instructions=[KIRPrintV0(expr=KIRStringV0(value="hello"))])
        raw = json.dumps(
            {
                "kind": "pipeline_bundle",
                "ast": {
                    "kind": "program",
                    "functions": [],
                    "statements": [
                        {"kind": "print", "expr": {"kind": "string", "value": "hello"}}
                    ],
                },
                "hir": {
                    "kind": "hir_program",
                    "functions": [],
                    "statements": [
                        {"kind": "print", "expr": {"kind": "string", "value": "hello"}}
                    ],
                },
                "kir": json.loads(serialize_kir_program_v0(kir)),
                "analysis": {
                    "kind": "analysis_v1",
                    "function_arities": {},
                    "effects": {"program": ["print"], "functions": {}},
                },
                "check": "ok",
                "artifact": {"kind": "print_many", "texts": ["hello"]},
                "compile": {"kind": "print_many", "texts": ["hello"]},
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )

        bundle = parse_selfhost_pipeline_bundle_v1(raw)
        self.assertEqual(bundle.kir.instructions[0].expr.value, "hello")
        self.assertEqual(
            json.loads(selfhost_pipeline_bundle_v1_to_json(bundle))["kir"],
            json.loads(serialize_kir_program_v0(kir)),
        )
