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
from kagi.subset import run_subset_program, run_subset_program_via_kir
import kagi.lower_subset_to_kir as lower_subset_to_kir
import kagi.subset as subset_module
import kagi.selfhost_runtime as selfhost_runtime
import kagi.subset_builtins as subset_builtins
import kagi.subset_typecheck as subset_typecheck
from kagi.surface_ast import parse_surface_program_v1


class BundleKirFutureTest(unittest.TestCase):
    def test_python_core_builtin_map_is_empty_after_stage5(self):
        self.assertEqual(subset_builtins.CORE_BUILTINS, {})

    def test_quote_builtin_is_removed_from_python_fallback_builtin_maps(self):
        self.assertNotIn("quote", subset_builtins.CORE_BUILTINS)
        self.assertNotIn("quote", subset_module.BUILTINS)
        self.assertNotIn("quote", lower_subset_to_kir.SUBSET_KIR_BUILTINS)
        self.assertNotIn("quote", subset_typecheck.BUILTIN_SIGNATURES)

    def test_selfhost_frontend_fallback_pipeline_still_runs_without_quote_builtin(self):
        root = Path(__file__).resolve().parents[1]
        frontend_source = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        source = (root / "examples" / "hello_arg_fn.ksrc").read_text(encoding="utf-8")

        expected = run_subset_program(frontend_source, entry="pipeline", args=[source])
        actual = run_subset_program_via_kir(frontend_source, entry="pipeline", args=[source])

        self.assertEqual(json.loads(actual), json.loads(expected))

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

        with patch("kagi.compile_result.execute_selfhost_frontend_pipeline_bundle_v1", return_value=bundle):
                compiled = compile_source_v1(frontend_source, "ignored source")

        self.assertEqual(compiled.lower.kir, kir)
        self.assertEqual(compiled.compile_kir, kir)

    def test_execute_selfhost_frontend_entry_v1_noncanonical_frontend_still_depends_on_python_host_path(self):
        frontend_source = "fn pipeline(source) { return source; }"
        source = "print \"hello\""

        with patch("kagi.selfhost_runtime.execute_subset_entry_via_kir_v0", side_effect=AssertionError("python host path is still required")):
            with self.assertRaisesRegex(AssertionError, "python host path is still required"):
                selfhost_runtime.execute_selfhost_frontend_entry_v1(frontend_source, entry="pipeline", args=[source])

    def test_execute_selfhost_frontend_entry_v1_canonical_frontend_does_not_use_python_kir_executor(self):
        root = Path(__file__).resolve().parents[1]
        frontend_source = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        source = (root / "examples" / "hello_arg_fn.ksrc").read_text(encoding="utf-8")

        with patch("kagi.selfhost_runtime.execute_kir_entry_v0", side_effect=AssertionError("python kir executor is still required")):
            value = selfhost_runtime.execute_selfhost_frontend_entry_v1(frontend_source, entry="pipeline", args=[source])
        self.assertIsInstance(value, str)
        self.assertIn('"kind":"pipeline_bundle"', value)

    def test_compile_source_v1_canonical_frontend_does_not_call_python_kir_executor(self):
        root = Path(__file__).resolve().parents[1]
        frontend_source = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        source = (root / "examples" / "hello_arg_fn.ksrc").read_text(encoding="utf-8")

        executor_spy = Mock(side_effect=AssertionError("python kir executor should not be used by canonical compile path"))
        with patch("kagi.selfhost_runtime.execute_kir_entry_v0", executor_spy):
            compiled = compile_source_v1(frontend_source, source)

        self.assertEqual(compiled.stdout, "hello, world!")
        self.assertEqual(executor_spy.call_count, 0)

    def test_compile_selfhost_frontend_to_kir_v1_canonical_frontend_does_not_reparse_subset_source(self):
        root = Path(__file__).resolve().parents[1]
        frontend_source = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")

        with patch("kagi.selfhost_runtime.parse_subset_program", side_effect=AssertionError("canonical freeze should not parse subset source")):
            with patch("kagi.selfhost_runtime.lower_subset_program_to_kir_v0", side_effect=AssertionError("canonical freeze should not lower subset source")):
                kir_json = selfhost_runtime.compile_selfhost_frontend_to_kir_v1(frontend_source)

        self.assertIsInstance(kir_json, str)
        self.assertIn('"kind":"kir"', kir_json)

    def test_execute_selfhost_frontend_entry_v1_canonical_frontend_uses_entry_snapshots(self):
        root = Path(__file__).resolve().parents[1]
        frontend_source = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        source = (root / "examples" / "hello_arg_fn.ksrc").read_text(encoding="utf-8")

        with patch("kagi.selfhost_runtime.execute_kir_entry_v0", wraps=selfhost_runtime.execute_kir_entry_v0) as executor_spy:
            value = selfhost_runtime.execute_selfhost_frontend_entry_v1(frontend_source, entry="pipeline", args=[source])

        self.assertIsInstance(value, str)
        self.assertEqual(executor_spy.call_count, 0)
        self.assertIn('"kind":"pipeline_bundle"', value)

    def test_compile_source_v1_noncanonical_frontend_still_depends_on_python_bundle_decoder(self):
        frontend_source = "fn pipeline(source) { return source; }"
        source = "print \"hello\""

        with patch("kagi.selfhost_runtime.parse_selfhost_pipeline_bundle_v1", side_effect=AssertionError("python bundle decoder is still required")):
            with self.assertRaisesRegex(AssertionError, "python bundle decoder is still required"):
                selfhost_runtime.execute_selfhost_frontend_pipeline_bundle_v1(frontend_source, source)

    def test_compile_source_v1_canonical_frontend_does_not_depend_on_python_bundle_decoder(self):
        root = Path(__file__).resolve().parents[1]
        frontend_source = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        source = (root / "examples" / "hello_arg_fn.ksrc").read_text(encoding="utf-8")

        with patch("kagi.selfhost_runtime.parse_selfhost_pipeline_bundle_v1", side_effect=AssertionError("python bundle decoder is still required")):
            bundle = selfhost_runtime.execute_selfhost_frontend_pipeline_bundle_v1(frontend_source, source)
        self.assertEqual(bundle.raw_check, "ok")

    def test_compile_source_v1_canonical_frontend_uses_typed_bundle_api(self):
        root = Path(__file__).resolve().parents[1]
        frontend_source = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        source = (root / "examples" / "hello_arg_fn.ksrc").read_text(encoding="utf-8")

        with patch("kagi.compile_result.execute_selfhost_frontend_pipeline_bundle_v1", wraps=selfhost_runtime.execute_selfhost_frontend_pipeline_bundle_v1) as bundle_api_spy:
            compiled = compile_source_v1(frontend_source, source)

        self.assertEqual(compiled.stdout, "hello, world!")
        self.assertEqual(bundle_api_spy.call_count, 1)
        self.assertEqual(bundle_api_spy.call_args.args, (frontend_source, source))
        self.assertEqual(compiled.metadata.frontend_entry, "pipeline")

    def test_cli_selfhost_run_canonical_frontend_uses_typed_bundle_api(self):
        root = Path(__file__).resolve().parents[1]
        frontend = root / "examples" / "selfhost_frontend.ks"
        source = root / "examples" / "hello_arg_fn.ksrc"

        import kagi.cli as cli_module
        import kagi.cli_host as cli_host_module

        argv = [
            "kagi",
            "selfhost-run",
            "--json",
            str(frontend),
            str(source),
        ]
        with patch.object(cli_host_module, "_selfhost_api") as api_spy:
            from kagi.selfhost_runtime import (
                build_selfhost_frontend_v1,
                compile_selfhost_frontend_to_kir_v1,
                execute_selfhost_frontend_entry_v1,
                execute_selfhost_frontend_pipeline_bundle_v1,
            )
            api_spy.return_value = (
                build_selfhost_frontend_v1,
                compile_selfhost_frontend_to_kir_v1,
                execute_selfhost_frontend_entry_v1,
                execute_selfhost_frontend_pipeline_bundle_v1,
            )
            with patch.object(cli_module, "emit_payload") as emit_spy:
                with patch("sys.argv", argv):
                    cli_module.main()
        payload = emit_spy.call_args.args[0]
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["entry"], "pipeline")
        self.assertEqual(payload["value"], "hello, world!")

    def test_cli_selfhost_run_canonical_frontend_does_not_depend_on_python_bundle_decoder(self):
        root = Path(__file__).resolve().parents[1]
        frontend = root / "examples" / "selfhost_frontend.ks"
        source = root / "examples" / "hello_arg_fn.ksrc"

        import kagi.cli as cli_module

        argv = [
            "kagi",
            "selfhost-run",
            "--json",
            str(frontend),
            str(source),
        ]
        with patch("kagi.selfhost_runtime.parse_selfhost_pipeline_bundle_v1", side_effect=AssertionError("python bundle decoder should not be used by canonical cli path")):
            with patch.object(cli_module, "emit_payload") as emit_spy:
                with patch("sys.argv", argv):
                    cli_module.main()
        payload = emit_spy.call_args.args[0]
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["value"], "hello, world!")

    def test_execute_selfhost_frontend_pipeline_bundle_v1_canonical_frontend_uses_entry_snapshots(self):
        root = Path(__file__).resolve().parents[1]
        frontend_source = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        source = (root / "examples" / "hello_arg_fn.ksrc").read_text(encoding="utf-8")

        with patch("kagi.selfhost_runtime.parse_selfhost_pipeline_bundle_v1", wraps=parse_selfhost_pipeline_bundle_v1) as bundle_spy:
            bundle = selfhost_runtime.execute_selfhost_frontend_pipeline_bundle_v1(frontend_source, source)

        self.assertEqual(bundle_spy.call_count, 0)
        self.assertEqual(bundle.raw_check, "ok")

    def test_compile_source_v1_canonical_frontend_does_not_call_python_string_helpers(self):
        root = Path(__file__).resolve().parents[1]
        frontend_source = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        helper_names = (
            "trim",
            "starts_with",
            "ends_with",
            "extract_quoted",
            "line_count",
            "line_at",
            "before_substring",
            "after_substring",
            "is_identifier",
        )
        cases = {
            "hello.ksrc": "hello, world!",
            "hello_concat.ksrc": "hello, world!",
            "hello_let.ksrc": "hello, world!",
            "hello_let_string.ksrc": "hello, world!",
            "hello_let_concat.ksrc": "hello, world!",
            "hello_twice.ksrc": "hello\nworld",
            "hello_fn.ksrc": "hello, world!",
            "hello_arg_fn.ksrc": "hello, world!",
            "hello_if.ksrc": "hello, world!",
            "hello_if_stmt.ksrc": "hello, world!",
            "hello_print_concat.ksrc": "hello, world!",
        }
        forbidden_helpers = {
            name: Mock(side_effect=AssertionError(f"{name} should not be used by canonical compile path"))
            for name in helper_names
        }

        with patch.object(
            selfhost_runtime,
            "SUBSET_KIR_BUILTINS",
            {
                **selfhost_runtime.SUBSET_KIR_BUILTINS,
                **forbidden_helpers,
            },
        ):
            for filename, expected_stdout in cases.items():
                with self.subTest(case=filename):
                    source = (root / "examples" / filename).read_text(encoding="utf-8")
                    compiled = compile_source_v1(frontend_source, source)
                    self.assertEqual(compiled.stdout, expected_stdout)

        for name, spy in forbidden_helpers.items():
            self.assertEqual(spy.call_count, 0, name)

    def test_compile_source_v1_canonical_frontend_does_not_call_python_core_expr_builtins(self):
        root = Path(__file__).resolve().parents[1]
        frontend_source = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        cases = {
            "hello_concat.ksrc": "hello, world!",
            "hello_let_concat.ksrc": "hello, world!",
            "hello_arg_fn.ksrc": "hello, world!",
            "hello_if.ksrc": "hello, world!",
            "hello_print_concat.ksrc": "hello, world!",
        }
        forbidden_helpers = {
            "concat": Mock(side_effect=AssertionError("concat should not be used by canonical compile path")),
            "eq": Mock(side_effect=AssertionError("eq should not be used by canonical compile path")),
        }

        with patch.object(
            selfhost_runtime,
            "SUBSET_KIR_BUILTINS",
            {
                **selfhost_runtime.SUBSET_KIR_BUILTINS,
                **forbidden_helpers,
            },
        ):
            for filename, expected_stdout in cases.items():
                with self.subTest(case=filename):
                    source = (root / "examples" / filename).read_text(encoding="utf-8")
                    compiled = compile_source_v1(frontend_source, source)
                    self.assertEqual(compiled.stdout, expected_stdout)

        for name, spy in forbidden_helpers.items():
            self.assertEqual(spy.call_count, 0, name)

    def test_canonical_frontend_entries_do_not_call_python_string_helpers(self):
        root = Path(__file__).resolve().parents[1]
        frontend_source = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        helper_names = (
            "trim",
            "starts_with",
            "ends_with",
            "extract_quoted",
            "line_count",
            "line_at",
            "before_substring",
            "after_substring",
            "is_identifier",
        )
        entries = ("parse", "hir", "kir", "analysis", "lower", "compile", "pipeline")
        cases = (
            "hello.ksrc",
            "hello_concat.ksrc",
            "hello_let.ksrc",
            "hello_let_string.ksrc",
            "hello_let_concat.ksrc",
            "hello_twice.ksrc",
            "hello_fn.ksrc",
            "hello_arg_fn.ksrc",
            "hello_if.ksrc",
            "hello_if_stmt.ksrc",
            "hello_print_concat.ksrc",
        )

        for entry in entries:
            for filename in cases:
                with self.subTest(entry=entry, case=filename):
                    source = (root / "examples" / filename).read_text(encoding="utf-8")
                    forbidden_helpers = {
                        name: Mock(side_effect=AssertionError(f"{name} should not be used by canonical {entry} path"))
                        for name in helper_names
                    }
                    with patch.object(
                        selfhost_runtime,
                        "SUBSET_KIR_BUILTINS",
                        {
                            **selfhost_runtime.SUBSET_KIR_BUILTINS,
                            **forbidden_helpers,
                        },
                    ):
                        value = selfhost_runtime.execute_selfhost_frontend_entry_v1(
                            frontend_source,
                            entry=entry,
                            args=[source],
                        )

                    self.assertIsInstance(value, str)
                    self.assertFalse(value.startswith("error:"))
                    for name, spy in forbidden_helpers.items():
                        self.assertEqual(spy.call_count, 0, f"{entry}:{filename}:{name}")

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

    def test_compile_source_v1_canonical_frontend_does_not_call_python_core_subset_builtins(self):
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
        forbidden_core_builtins = {
            name: Mock(side_effect=AssertionError(f"{name} should not be used by canonical compile path"))
            for name in subset_builtins.CORE_BUILTINS
        }

        with patch.object(
            selfhost_runtime,
            "SUBSET_KIR_BUILTINS",
            {
                **selfhost_runtime.SUBSET_KIR_BUILTINS,
                **forbidden_core_builtins,
            },
        ):
            for filename, expected_stdout in cases.items():
                with self.subTest(case=filename):
                    source = (root / "examples" / filename).read_text(encoding="utf-8")
                    compiled = compile_source_v1(frontend_source, source)
                    self.assertEqual(compiled.stdout, expected_stdout)

        for name, spy in forbidden_core_builtins.items():
            self.assertEqual(spy.call_count, 0, name)

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
            "print_many_artifact",
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
            "quote",
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

    def test_canonical_frontend_parse_does_not_call_python_bootstrap_builders(self):
        root = Path(__file__).resolve().parents[1]
        frontend_source = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        cases = (
            "hello.ksrc",
            "hello_print_concat.ksrc",
            "hello_let_string.ksrc",
            "hello_let_concat.ksrc",
            "hello_twice.ksrc",
            "hello_fn.ksrc",
            "hello_arg_fn.ksrc",
            "hello_if.ksrc",
            "hello_if_stmt.ksrc",
        )
        forbidden_builder_names = (
            "print_many_artifact",
            "program_ast",
            "program_if_expr_print_ast",
            "program_if_stmt_ast",
            "program_print_concat_ast",
            "program_let_concat_print_ast",
            "program_single_arg_fn_call_ast",
            "program_let_print_ast",
            "program_two_prints_ast",
            "program_zero_arg_fn_call_ast",
            "quote",
        )

        for filename in cases:
            with self.subTest(case=filename):
                source = (root / "examples" / filename).read_text(encoding="utf-8")
                forbidden_builtins = {
                    name: Mock(side_effect=AssertionError(f"{name} should not be used by canonical parse path"))
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
                    value = selfhost_runtime.execute_selfhost_frontend_entry_v1(
                        frontend_source,
                        entry="parse",
                        args=[source],
                    )

                self.assertIsInstance(value, str)
                self.assertFalse(value.startswith("error:"))
                for name, spy in forbidden_builtins.items():
                    self.assertEqual(spy.call_count, 0, f"{filename}:{name}")

    def test_canonical_frontend_hello_twice_does_not_call_print_many_artifact_in_lower_compile_path(self):
        root = Path(__file__).resolve().parents[1]
        frontend_source = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        source = (root / "examples" / "hello_twice.ksrc").read_text(encoding="utf-8")
        print_many_spy = Mock(side_effect=AssertionError("print_many_artifact should not be used by canonical lower/compile path"))

        with patch.object(
            selfhost_runtime,
            "SUBSET_KIR_BUILTINS",
            {
                **selfhost_runtime.SUBSET_KIR_BUILTINS,
                "print_many_artifact": print_many_spy,
            },
        ):
            lowered = selfhost_runtime.execute_selfhost_frontend_entry_v1(
                frontend_source,
                entry="lower",
                args=[source],
            )
            compiled = selfhost_runtime.execute_selfhost_frontend_entry_v1(
                frontend_source,
                entry="compile",
                args=[source],
            )
            pipeline = selfhost_runtime.execute_selfhost_frontend_entry_v1(
                frontend_source,
                entry="pipeline",
                args=[source],
            )
            bundle_compiled = compile_source_v1(frontend_source, source)

        self.assertEqual(json.loads(lowered), {"kind": "print_many", "texts": ["hello", "world"]})
        self.assertEqual(json.loads(compiled), {"kind": "print_many", "texts": ["hello", "world"]})
        self.assertEqual(json.loads(pipeline)["artifact"], {"kind": "print_many", "texts": ["hello", "world"]})
        self.assertEqual(bundle_compiled.stdout, "hello\nworld")
        self.assertEqual(print_many_spy.call_count, 0)

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
