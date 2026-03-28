import unittest
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import json
from contextlib import ExitStack, redirect_stdout
from unittest.mock import patch

import kagi
import kagi.cli as cli_module
import kagi.kir_runtime as kir_runtime_module
import kagi.selfhost_runtime as selfhost_runtime_module
from kagi.compile_result import compile_source_v1
from kagi.capir_runtime import (
    capir_fragment_from_artifact,
    capir_fragment_from_kir_program,
    execute_and_inspect_capir_artifact,
    execute_capir_artifact,
    execute_capir_fragment,
    execute_kir_program as execute_kir_program_result,
    inspect_capir_artifact,
    kir_program_to_artifact,
)
from kagi.diagnostics import DiagnosticError
from kagi.frontend import execute_bootstrap_program, parse_bootstrap_program, parse_core_program
from kagi.ir import serialize_capir_fragment, serialize_program_ir
from kagi.kir import (
    KIRCallV0,
    KIRConcatV0,
    KIREqV0,
    KIRFunctionV0,
    KIRIfStmtV0,
    KIRLetV0,
    KIRPrintV0,
    KIRProgramV0,
    KIRReturnV0,
    KIRStringV0,
    KIRVarV0,
    inspect_kir_artifact,
    kir_program_from_print_artifact,
    serialize_kir_program_v0,
)
from kagi.selfhost_bundle import parse_selfhost_pipeline_bundle_v1, selfhost_pipeline_bundle_v1_to_json
import kagi.subset as subset_module
from kagi.subset import parse_subset_program, run_subset_program, run_subset_program_via_kir
from kagi.artifact import parse_artifact_v1
from kagi.runtime import (
    Cell,
    KagiRuntimeError,
    LoanState,
    apply_action,
    export_owner,
    execute_program_ir,
    well_formed,
)
from kagi.ir import Action
from kagi.kir_runtime import execute_kir_program_v0


class RuntimeTest(unittest.TestCase):
    def test_well_formed_rejects_dead_owner_with_outstanding_loan(self):
        heap = {0: Cell(alive=False, loan=LoanState.mut(7))}
        self.assertFalse(well_formed(heap))

    def test_shared_same_epoch_can_extend_and_export_hides_reader_count(self):
        heap = {0: Cell(alive=True, loan=LoanState.shared(10, 0))}
        next_heap = apply_action(heap, Action("borrow_shared", 0, 10))
        self.assertEqual(next_heap[0].loan, LoanState.shared(10, 1))
        self.assertEqual(export_owner(next_heap, 0), "shared 10")

    def test_shared_foreign_epoch_is_blocked(self):
        heap = {0: Cell(alive=True, loan=LoanState.shared(10, 0))}
        with self.assertRaises(KagiRuntimeError):
            apply_action(heap, Action("borrow_shared", 0, 11))

    def test_busy_owner_blocks_mut_and_drop(self):
        heap = {0: Cell(alive=True, loan=LoanState.shared(10, 0))}
        with self.assertRaises(KagiRuntimeError):
            apply_action(heap, Action("borrow_mut", 0, 5))
        with self.assertRaises(KagiRuntimeError):
            apply_action(heap, Action("drop", 0))

    def test_program_execution(self):
        source = """
        owner 0 alive idle
        owner 1 alive idle
        borrow_shared 0 9
        borrow_shared 0 9
        end_shared 0 9
        borrow_mut 1 7
        end_mut 1 7
        drop 1
        """
        result = execute_program_ir(parse_core_program(source))
        self.assertEqual(result.heap[0].loan, LoanState.shared(9, 0))
        self.assertFalse(result.heap[1].alive)
        self.assertEqual(export_owner(result.heap, 0), "shared 9")
        self.assertEqual(export_owner(result.heap, 1), "idle")

    def test_execution_result_keeps_actions(self):
        result = execute_program_ir(parse_core_program(
            """
            owner 0 alive idle
            borrow_mut 0 3
            end_mut 0 3
            """
        ))
        self.assertEqual(len(result.actions), 2)
        self.assertEqual(result.actions[0].kind, "borrow_mut")

    def test_capir_roundtrip_for_core_example(self):
        source = """
        owner 0 alive idle
        owner 1 alive idle
        borrow_shared 0 9
        end_shared 0 9
        """
        program = parse_core_program(source)
        serialized = serialize_program_ir(program)
        reparsed = parse_core_program(serialized)
        self.assertEqual(serialized, serialize_program_ir(reparsed))

    def test_bootstrap_program_supports_named_symbols_and_assertions(self):
        program = parse_bootstrap_program(
            """
            let epoch e0 = 10
            let key k0 = 7
            owner cell alive idle
            borrow_shared cell e0
            assert_export cell shared e0
            end_shared cell e0
            borrow_mut cell k0
            assert_export cell mut
            end_mut cell k0
            """
        )
        self.assertEqual(program.owner_ids["cell"], 0)
        self.assertEqual(len(program.program.actions), 4)
        self.assertEqual(len(program.assertions), 2)

    def test_capir_roundtrip_for_bootstrap_example(self):
        source = """
        let epoch e0 = 10
        owner cell alive idle
        borrow_shared cell e0
        """
        program = parse_bootstrap_program(source)
        serialized = serialize_program_ir(program.program)
        reparsed = parse_core_program(serialized)
        self.assertEqual(serialized, serialize_program_ir(reparsed))

    def test_examples_roundtrip_via_capir(self):
        root = Path(__file__).resolve().parents[1]

        core_source = (root / "examples" / "basic.kagi").read_text(encoding="utf-8")
        core_program = parse_core_program(core_source)
        core_serialized = serialize_program_ir(core_program)
        self.assertEqual(core_serialized, serialize_program_ir(parse_core_program(core_serialized)))

        bootstrap_source = (root / "examples" / "bootstrap.kg").read_text(encoding="utf-8")
        bootstrap_program = parse_bootstrap_program(bootstrap_source)
        bootstrap_serialized = serialize_program_ir(bootstrap_program.program)
        self.assertEqual(bootstrap_serialized, serialize_program_ir(parse_core_program(bootstrap_serialized)))

    def test_bootstrap_execution_runs_and_checks_assertions(self):
        result = execute_bootstrap_program(
            """
            let epoch e0 = 9
            owner cell alive idle
            borrow_shared cell e0
            assert_export cell shared e0
            """
        )
        self.assertEqual(export_owner(result.heap, 0), "shared 9")

    def test_core_parse_error_exposes_structured_diagnostic(self):
        with self.assertRaises(DiagnosticError) as ctx:
            parse_core_program(
                """
                owner 0 alive idle
                borrow_mut nope
                """
            )
        diagnostic = ctx.exception.diagnostic
        self.assertEqual(diagnostic.phase, "parse")
        self.assertEqual(diagnostic.code, "parse_error")
        self.assertEqual(diagnostic.line, 3)
        self.assertEqual(diagnostic.snippet.strip(), "borrow_mut nope")

    def test_bootstrap_assertion_failure_exposes_structured_diagnostic(self):
        with self.assertRaises(DiagnosticError) as ctx:
            execute_bootstrap_program(
                """
                let epoch e0 = 9
                owner cell alive idle
                borrow_shared cell e0
                assert_export cell idle
                """
            )
        diagnostic = ctx.exception.diagnostic
        self.assertEqual(diagnostic.phase, "assert")
        self.assertEqual(diagnostic.code, "assert_export_failed")

    def test_cli_json_error_format_is_structured(self):
        root = Path(__file__).resolve().parents[1]
        invalid = root / "tests" / "_invalid_parse.kagi"
        invalid.write_text("owner 0 alive idle\nborrow_mut nope\n", encoding="utf-8")
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "kagi.cli", "check", "--json", str(invalid)],
                cwd=root,
                env={"PYTHONPATH": str(root / "src")},
                capture_output=True,
                text=True,
                check=False,
            )
        finally:
            invalid.unlink(missing_ok=True)

        self.assertEqual(proc.returncode, 1)
        payload = __import__("json").loads(proc.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["diagnostic"]["phase"], "parse")
        self.assertEqual(payload["diagnostic"]["code"], "parse_error")

    def test_subset_program_runs_minimal_function_language(self):
        source = """
        fn main(name) {
            let prefix = "hello, ";
            return concat(prefix, name);
        }
        """
        program = parse_subset_program(source)
        self.assertEqual(len(program.functions), 1)
        value = run_subset_program(source, entry="main", args=["world!"])
        self.assertEqual(value, "hello, world!")

    def test_subset_program_via_kir_matches_interpreter(self):
        source = """
        fn main(name) {
            let prefix = "hello, ";
            return concat(prefix, name);
        }
        """
        expected = run_subset_program(source, entry="main", args=["world!"])
        actual = run_subset_program_via_kir(source, entry="main", args=["world!"])
        self.assertEqual(actual, expected)

    def test_subset_program_via_kir_does_not_need_concat_or_eq_builtins(self):
        source = """
        fn main(name) {
            let prefix = "hello, ";
            let greeting = concat(prefix, name);
            if eq(greeting, "hello, world!") {
                return greeting;
            } else {
                return "no";
            }
        }
        """
        patched_builtins = {
            **subset_module.BUILTINS,
            "concat": lambda *_args: (_ for _ in ()).throw(AssertionError("concat builtin should not be used by subset KIR path")),
            "eq": lambda *_args: (_ for _ in ()).throw(AssertionError("eq builtin should not be used by subset KIR path")),
        }
        with patch("kagi.lower_subset_to_kir.SUBSET_KIR_BUILTINS", patched_builtins):
            actual = run_subset_program_via_kir(source, entry="main", args=["world!"])
        self.assertEqual(actual, "hello, world!")

    def test_subset_program_via_kir_does_not_call_python_kir_entry_runtime_for_builtin_free_function_path(self):
        source = """
        fn suffix(name) {
            return concat(name, "!");
        }

        fn main(name) {
            let greeting = suffix(name);
            if eq(greeting, "hello!") {
                return greeting;
            } else {
                return "no";
            }
        }
        """
        with patch("kagi.kir_runtime.execute_kir_entry_v0", side_effect=AssertionError("subset KIR entry should not use python kir runtime")):
            actual = run_subset_program_via_kir(source, entry="main", args=["hello"])
        self.assertEqual(actual, "hello!")

    def test_selfhost_pipeline_via_kir_matches_interpreter(self):
        root = Path(__file__).resolve().parents[1]
        frontend = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        source = (root / "examples" / "hello_arg_fn.ksrc").read_text(encoding="utf-8")

        expected = run_subset_program(frontend, entry="pipeline", args=[source])
        actual = run_subset_program_via_kir(frontend, entry="pipeline", args=[source])

        self.assertEqual(json.loads(actual), json.loads(expected))

    def test_selfhost_runtime_execute_kir_entry_uses_local_fast_path_for_builtin_free_program(self):
        program = KIRProgramV0(
            instructions=[],
            functions=[
                KIRFunctionV0(
                    name="main",
                    params=["name"],
                    body=[
                        KIRLetV0(name="greeting", expr=KIRConcatV0(left=KIRVarV0(name="name"), right=KIRStringV0(value="!"))),
                        KIRReturnV0(expr=KIRVarV0(name="greeting")),
                    ],
                )
            ],
        )
        with patch("kagi.kir_runtime.execute_kir_entry_v0", side_effect=AssertionError("selfhost KIR entry should not use python kir runtime")):
            actual = selfhost_runtime_module.execute_kir_entry_v0(program, entry="main", args=["hello"], builtins={})
        self.assertEqual(actual, "hello!")

    def test_kagi_subset_module_exports_run_subset_program_via_kir(self):
        self.assertTrue(callable(run_subset_program_via_kir))

    def test_import_kagi_package_does_not_eagerly_load_kir_runtime(self):
        root = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys, kagi; print('kagi.kir_runtime' in sys.modules)",
            ],
            cwd=root,
            env={"PYTHONPATH": str(root / "src")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "False")

    def test_import_kagi_cli_does_not_eagerly_load_kir_runtime(self):
        root = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys, kagi.cli; print('kagi.kir_runtime' in sys.modules)",
            ],
            cwd=root,
            env={"PYTHONPATH": str(root / "src")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "False")

    def test_kir_program_to_artifact_rejects_non_print_only_program(self):
        program = KIRProgramV0(
            instructions=[
                KIRLetV0(name="greeting", expr=KIRStringV0(value="hello")),
                KIRReturnV0(expr=KIRStringV0(value="bye")),
            ]
        )
        with self.assertRaises(DiagnosticError):
            kir_program_to_artifact(program)
        with self.assertRaises(DiagnosticError):
            capir_fragment_from_kir_program(program)

    def test_execute_kir_program_helper_matches_runtime_for_richer_kir(self):
        program = KIRProgramV0(
            instructions=[KIRCallV0(name="emit_suffix", args=[KIRStringV0(value="hello, world")])],
            functions=[
                KIRFunctionV0(
                    name="emit_suffix",
                    params=["name"],
                    body=[
                        KIRLetV0(name="suffix", expr=KIRStringV0(value="!")),
                        KIRPrintV0(
                            expr=KIRConcatV0(
                                left=KIRVarV0(name="name"),
                                right=KIRVarV0(name="suffix"),
                            )
                        ),
                    ],
                )
            ],
        )
        expected = execute_kir_program_v0(program, builtins=subset_module.BUILTINS).output
        actual = execute_kir_program_result(program).output
        self.assertEqual(actual, expected)

    def test_execute_kir_program_helper_does_not_call_python_kir_runtime_for_print_program(self):
        program = KIRProgramV0(instructions=[KIRPrintV0(expr=KIRStringV0(value="hello"))], functions=[])
        with patch("kagi.capir_runtime.execute_kir_program_v0", side_effect=AssertionError("capir helper should not use python kir runtime")):
            actual = execute_kir_program_result(program).output
        self.assertEqual(actual, "hello")

    def test_execute_kir_program_v0_print_only_uses_artifact_fast_path(self):
        program = KIRProgramV0(
            instructions=[
                KIRPrintV0(expr=KIRStringV0(value="hello")),
                KIRPrintV0(expr=KIRStringV0(value="world")),
            ],
            functions=[],
        )
        with patch.object(
            kir_runtime_module,
            "_execute_generic_kir_program_v0",
            side_effect=AssertionError("generic kir executor should not be used for print-only programs"),
        ):
            result = execute_kir_program_v0(program)
        self.assertEqual(result.output, "hello\nworld")

    def test_execute_kir_program_v0_richer_program_still_uses_generic_fallback(self):
        program = KIRProgramV0(
            instructions=[
                KIRLetV0(name="greeting", expr=KIRStringV0(value="hello")),
                KIRPrintV0(expr=KIRVarV0(name="greeting")),
            ],
            functions=[],
        )
        with patch.object(
            kir_runtime_module,
            "_execute_generic_kir_program_v0",
            wraps=kir_runtime_module._execute_generic_kir_program_v0,
        ) as generic_spy:
            result = execute_kir_program_v0(program)
        self.assertEqual(result.output, "hello")
        self.assertEqual(generic_spy.call_count, 1)

    def test_execute_kir_program_helper_does_not_call_python_kir_runtime_for_closed_let_print_program(self):
        program = KIRProgramV0(
            instructions=[
                KIRLetV0(name="greeting", expr=KIRStringV0(value="hello")),
                KIRPrintV0(expr=KIRVarV0(name="greeting")),
            ],
            functions=[],
        )
        with patch("kagi.kir_runtime.execute_kir_program_v0", side_effect=AssertionError("closed KIR helper should not use python kir runtime")):
            actual = execute_kir_program_result(program).output
        self.assertEqual(actual, "hello")

    def test_execute_kir_program_helper_does_not_call_python_kir_runtime_for_closed_if_program(self):
        program = KIRProgramV0(
            instructions=[
                KIRLetV0(name="greeting", expr=KIRConcatV0(left=KIRStringV0(value="hello, "), right=KIRStringV0(value="world!"))),
                KIRIfStmtV0(
                    condition=KIREqV0(left=KIRVarV0(name="greeting"), right=KIRStringV0(value="hello, world!")),
                    then_body=[KIRPrintV0(expr=KIRVarV0(name="greeting"))],
                    else_body=[KIRPrintV0(expr=KIRStringV0(value="no"))],
                ),
            ],
            functions=[],
        )
        with patch("kagi.kir_runtime.execute_kir_program_v0", side_effect=AssertionError("closed KIR helper should not use python kir runtime")):
            actual = execute_kir_program_result(program).output
        self.assertEqual(actual, "hello, world!")

    def test_subset_builtins_program_ast_matches_current_shape(self):
        source = """
        fn main() {
            return program_ast("hello, world!");
        }
        """
        value = run_subset_program(source, entry="main", args=[])
        self.assertEqual(
            json.loads(value),
            {
                "kind": "program",
                "functions": [],
                "statements": [
                    {"kind": "print", "expr": {"kind": "string", "value": "hello, world!"}},
                ],
            },
        )

    def test_subset_builtins_program_let_print_ast_matches_current_shape(self):
        source = """
        fn main() {
            return program_let_print_ast("greeting", "hello, world!");
        }
        """
        value = run_subset_program(source, entry="main", args=[])
        self.assertEqual(
            json.loads(value),
            {
                "kind": "program",
                "functions": [],
                "statements": [
                    {"kind": "let", "name": "greeting", "expr": {"kind": "string", "value": "hello, world!"}},
                    {"kind": "print", "expr": {"kind": "var", "name": "greeting"}},
                ],
            },
        )

    def test_subset_builtins_program_let_concat_print_ast_matches_current_shape(self):
        source = """
        fn main() {
            return program_let_concat_print_ast("greeting", "hello, ", "world!");
        }
        """
        value = run_subset_program(source, entry="main", args=[])
        self.assertEqual(
            json.loads(value),
            {
                "kind": "program",
                "functions": [],
                "statements": [
                    {
                        "kind": "let",
                        "name": "greeting",
                        "expr": {
                            "kind": "concat",
                            "left": {"kind": "string", "value": "hello, "},
                            "right": {"kind": "string", "value": "world!"},
                        },
                    },
                    {"kind": "print", "expr": {"kind": "var", "name": "greeting"}},
                ],
            },
        )

    def test_subset_builtins_program_print_concat_ast_matches_current_shape(self):
        source = """
        fn main() {
            return program_print_concat_ast("hello, ", "world!");
        }
        """
        value = run_subset_program(source, entry="main", args=[])
        self.assertEqual(
            json.loads(value),
            {
                "kind": "program",
                "functions": [],
                "statements": [
                    {
                        "kind": "print",
                        "expr": {
                            "kind": "concat",
                            "left": {"kind": "string", "value": "hello, "},
                            "right": {"kind": "string", "value": "world!"},
                        },
                    }
                ],
            },
        )

    def test_subset_builtins_program_single_arg_fn_call_ast_matches_current_shape(self):
        source = """
        fn main() {
            return program_single_arg_fn_call_ast("emit_suffix", "name", "hello, world", "!");
        }
        """
        value = run_subset_program(source, entry="main", args=[])
        self.assertEqual(
            json.loads(value),
            {
                "kind": "program",
                "functions": [
                    {
                        "kind": "fn",
                        "name": "emit_suffix",
                        "params": ["name"],
                        "body": [
                            {
                                "kind": "print",
                                "expr": {
                                    "kind": "concat",
                                    "left": {"kind": "var", "name": "name"},
                                    "right": {"kind": "string", "value": "!"},
                                },
                            }
                        ],
                    }
                ],
                "statements": [
                    {
                        "kind": "call",
                        "name": "emit_suffix",
                        "args": [{"kind": "string", "value": "hello, world"}],
                    }
                ],
            },
        )

    def test_subset_builtins_print_many_artifact_shape(self):
        source = """
        fn main() {
            return print_many_artifact("hello, world!");
        }
        """
        value = run_subset_program(source, entry="main", args=[])
        self.assertEqual(json.loads(value), {"kind": "print_many", "texts": ["hello, world!"]})

    def test_selfhost_frontend_emits_hello_world(self):
        root = Path(__file__).resolve().parents[1]
        frontend = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        source = (root / "examples" / "hello.ksrc").read_text(encoding="utf-8")
        bundle = run_subset_program(frontend, entry="pipeline", args=[source])
        ast = run_subset_program(frontend, entry="parse", args=[source])
        checked = run_subset_program(frontend, entry="check", args=[source])
        lowered = run_subset_program(frontend, entry="lower", args=[source])
        compiled = run_subset_program(frontend, entry="compile", args=[source])
        bundle_json = json.loads(bundle)
        self.assertEqual(
            bundle_json,
            {
                "kind": "pipeline_bundle",
                "ast": json.loads(ast),
                "hir": {
                    "kind": "hir_program",
                    "functions": [],
                    "statements": [
                        {"kind": "print", "expr": {"kind": "string", "value": "hello, world!"}},
                    ],
                },
                "kir": {
                    "kind": "kir",
                    "functions": [],
                    "instructions": [
                        {"op": "print", "expr": {"kind": "string", "value": "hello, world!"}},
                    ],
                },
                "analysis": {
                    "kind": "analysis_v1",
                    "function_arities": {},
                    "effects": {"program": ["print"], "functions": {}},
                },
                "check": "ok",
                "artifact": json.loads(lowered),
                "compile": json.loads(compiled),
            },
        )
        self.assertEqual(
            json.loads(ast),
            {
                "kind": "program",
                "functions": [],
                "statements": [
                    {"kind": "print", "expr": {"kind": "string", "value": "hello, world!"}},
                ],
            },
        )
        self.assertEqual(checked, "ok")
        self.assertEqual(json.loads(lowered), {"kind": "print_many", "texts": ["hello, world!"]})
        self.assertEqual(json.loads(compiled), {"kind": "print_many", "texts": ["hello, world!"]})
        capir = capir_fragment_from_artifact(lowered)
        self.assertEqual(capir.effect, "print")
        self.assertEqual(serialize_capir_fragment(capir), 'print "hello, world!"\n')
        self.assertEqual(execute_capir_artifact(lowered).output, "hello, world!")

    def test_selfhost_frontend_supports_multiple_print_statements(self):
        root = Path(__file__).resolve().parents[1]
        frontend = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        source = (root / "examples" / "hello_twice.ksrc").read_text(encoding="utf-8")
        ast = run_subset_program(frontend, entry="parse", args=[source])
        checked = run_subset_program(frontend, entry="check", args=[source])
        lowered = run_subset_program(frontend, entry="lower", args=[source])

        self.assertEqual(
            json.loads(ast),
            {
                "kind": "program",
                "functions": [],
                "statements": [
                    {"kind": "print", "expr": {"kind": "string", "value": "hello"}},
                    {"kind": "print", "expr": {"kind": "string", "value": "world"}},
                ],
            },
        )
        self.assertEqual(checked, "ok")
        self.assertEqual(json.loads(lowered), {"kind": "print_many", "texts": ["hello", "world"]})
        capir = capir_fragment_from_artifact(lowered)
        self.assertEqual(serialize_capir_fragment(capir), 'print "hello"\nprint "world"\n')
        self.assertEqual(execute_capir_artifact(lowered).output, "hello\nworld")

    def test_selfhost_frontend_supports_concat_print_expression(self):
        root = Path(__file__).resolve().parents[1]
        frontend = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        source = (root / "examples" / "hello_concat.ksrc").read_text(encoding="utf-8")
        ast = run_subset_program(frontend, entry="parse", args=[source])
        lowered = run_subset_program(frontend, entry="lower", args=[source])
        self.assertEqual(
            json.loads(ast),
            {
                "kind": "program",
                "functions": [],
                "statements": [
                    {
                        "kind": "print",
                        "expr": {
                            "kind": "concat",
                            "left": {"kind": "string", "value": "hello, "},
                            "right": {"kind": "string", "value": "world!"},
                        },
                    }
                ],
            },
        )
        self.assertEqual(json.loads(lowered), {"kind": "print_many", "texts": ["hello, world!"]})

    def test_selfhost_frontend_selfhosts_simple_print_concat(self):
        root = Path(__file__).resolve().parents[1]
        frontend = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        source = (root / "examples" / "hello_print_concat.ksrc").read_text(encoding="utf-8")
        ast = run_subset_program(frontend, entry="parse", args=[source])
        self.assertEqual(
            json.loads(ast),
            {
                "kind": "program",
                "functions": [],
                "statements": [
                    {
                        "kind": "print",
                        "expr": {
                            "kind": "concat",
                            "left": {"kind": "string", "value": "hello, "},
                            "right": {"kind": "string", "value": "world!"},
                        },
                    }
                ],
            },
        )

    def test_selfhost_frontend_supports_let_and_var_print(self):
        root = Path(__file__).resolve().parents[1]
        frontend = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        source = (root / "examples" / "hello_let.ksrc").read_text(encoding="utf-8")
        ast = run_subset_program(frontend, entry="parse", args=[source])
        lowered = run_subset_program(frontend, entry="lower", args=[source])
        self.assertEqual(
            json.loads(ast),
            {
                "kind": "program",
                "functions": [],
                "statements": [
                    {
                        "kind": "let",
                        "name": "greeting",
                        "expr": {
                            "kind": "concat",
                            "left": {"kind": "string", "value": "hello, "},
                            "right": {"kind": "string", "value": "world!"},
                        },
                    },
                    {"kind": "print", "expr": {"kind": "var", "name": "greeting"}},
                ],
            },
        )
        self.assertEqual(json.loads(lowered), {"kind": "print_many", "texts": ["hello, world!"]})

    def test_selfhost_frontend_selfhosts_simple_let_string_print(self):
        root = Path(__file__).resolve().parents[1]
        frontend = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        source = (root / "examples" / "hello_let_string.ksrc").read_text(encoding="utf-8")
        ast = run_subset_program(frontend, entry="parse", args=[source])
        self.assertEqual(
            json.loads(ast),
            {
                "kind": "program",
                "functions": [],
                "statements": [
                    {"kind": "let", "name": "greeting", "expr": {"kind": "string", "value": "hello, world!"}},
                    {"kind": "print", "expr": {"kind": "var", "name": "greeting"}},
                ],
            },
        )

    def test_selfhost_frontend_selfhosts_simple_let_concat_print(self):
        root = Path(__file__).resolve().parents[1]
        frontend = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        source = (root / "examples" / "hello_let_concat.ksrc").read_text(encoding="utf-8")
        ast = run_subset_program(frontend, entry="parse", args=[source])
        self.assertEqual(
            json.loads(ast),
            {
                "kind": "program",
                "functions": [],
                "statements": [
                    {
                        "kind": "let",
                        "name": "greeting",
                        "expr": {
                            "kind": "concat",
                            "left": {"kind": "string", "value": "hello, "},
                            "right": {"kind": "string", "value": "world!"},
                        },
                    },
                    {"kind": "print", "expr": {"kind": "var", "name": "greeting"}},
                ],
            },
        )

    def test_capir_fragment_can_be_recovered_from_selfhost_artifact(self):
        artifact = '{"kind":"print_many","texts":["hello","world"]}'
        fragment = capir_fragment_from_artifact(artifact)
        self.assertEqual(fragment.effect, "print")
        self.assertEqual([op.text for op in fragment.ops], ["hello", "world"])
        self.assertEqual(execute_capir_fragment(fragment).output, "hello\nworld")

    def test_capir_artifact_can_be_executed_directly(self):
        artifact = '{"kind":"print_many","texts":["hello","world"]}'
        self.assertEqual(execute_capir_artifact(artifact).output, "hello\nworld")

    def test_selfhost_frontend_supports_if_and_eq_expression(self):
        root = Path(__file__).resolve().parents[1]
        frontend = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        source = (root / "examples" / "hello_if.ksrc").read_text(encoding="utf-8")
        ast = run_subset_program(frontend, entry="parse", args=[source])
        lowered = run_subset_program(frontend, entry="lower", args=[source])
        self.assertEqual(
            json.loads(ast),
            {
                "kind": "program",
                "functions": [],
                "statements": [
                    {
                        "kind": "let",
                        "name": "greeting",
                        "expr": {
                            "kind": "concat",
                            "left": {"kind": "string", "value": "hello, "},
                            "right": {"kind": "string", "value": "world!"},
                        },
                    },
                    {
                        "kind": "let",
                        "name": "enabled",
                        "expr": {
                            "kind": "eq",
                            "left": {"kind": "var", "name": "greeting"},
                            "right": {"kind": "string", "value": "hello, world!"},
                        },
                    },
                    {
                        "kind": "print",
                        "expr": {
                            "kind": "if",
                            "condition": {"kind": "var", "name": "enabled"},
                            "then": {"kind": "var", "name": "greeting"},
                            "else": {"kind": "string", "value": "disabled"},
                        },
                    },
                ],
            },
        )
        self.assertEqual(json.loads(lowered), {"kind": "print_many", "texts": ["hello, world!"]})

    def test_selfhost_frontend_covered_current_shapes_do_not_depend_on_legacy_subset_builtins(self):
        root = Path(__file__).resolve().parents[1]
        frontend = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        saved_builtins = subset_module.BUILTINS.copy()
        for builtin_name in ("parse_print_program", "validate_program_ast", "lower_program_artifact"):
            subset_module.BUILTINS.pop(builtin_name, None)
        try:
            cases = [
                (
                    "hello_twice.ksrc",
                    {
                        "kind": "program",
                        "functions": [],
                        "statements": [
                            {"kind": "print", "expr": {"kind": "string", "value": "hello"}},
                            {"kind": "print", "expr": {"kind": "string", "value": "world"}},
                        ],
                    },
                    {"kind": "print_many", "texts": ["hello", "world"]},
                    "hello\nworld",
                ),
                (
                    "hello_fn.ksrc",
                    {
                        "kind": "program",
                        "functions": [
                            {
                                "kind": "fn",
                                "name": "emit_greeting",
                                "params": [],
                                "body": [
                                    {
                                        "kind": "let",
                                        "name": "greeting",
                                        "expr": {
                                            "kind": "concat",
                                            "left": {"kind": "string", "value": "hello, "},
                                            "right": {"kind": "string", "value": "world!"},
                                        },
                                    },
                                    {"kind": "print", "expr": {"kind": "var", "name": "greeting"}},
                                ],
                            }
                        ],
                        "statements": [{"kind": "call", "name": "emit_greeting", "args": []}],
                    },
                    {"kind": "print_many", "texts": ["hello, world!"]},
                    "hello, world!",
                ),
                (
                    "hello_if.ksrc",
                    {
                        "kind": "program",
                        "functions": [],
                        "statements": [
                            {
                                "kind": "let",
                                "name": "greeting",
                                "expr": {
                                    "kind": "concat",
                                    "left": {"kind": "string", "value": "hello, "},
                                    "right": {"kind": "string", "value": "world!"},
                                },
                            },
                            {
                                "kind": "let",
                                "name": "enabled",
                                "expr": {
                                    "kind": "eq",
                                    "left": {"kind": "var", "name": "greeting"},
                                    "right": {"kind": "string", "value": "hello, world!"},
                                },
                            },
                            {
                                "kind": "print",
                                "expr": {
                                    "kind": "if",
                                    "condition": {"kind": "var", "name": "enabled"},
                                    "then": {"kind": "var", "name": "greeting"},
                                    "else": {"kind": "string", "value": "disabled"},
                                },
                            },
                        ],
                    },
                    {"kind": "print_many", "texts": ["hello, world!"]},
                    "hello, world!",
                ),
                (
                    "hello_if_stmt.ksrc",
                    {
                        "kind": "program",
                        "functions": [],
                        "statements": [
                            {
                                "kind": "let",
                                "name": "greeting",
                                "expr": {
                                    "kind": "concat",
                                    "left": {"kind": "string", "value": "hello, "},
                                    "right": {"kind": "string", "value": "world!"},
                                },
                            },
                            {
                                "kind": "let",
                                "name": "enabled",
                                "expr": {
                                    "kind": "eq",
                                    "left": {"kind": "var", "name": "greeting"},
                                    "right": {"kind": "string", "value": "hello, world!"},
                                },
                            },
                            {
                                "kind": "if_stmt",
                                "condition": {"kind": "var", "name": "enabled"},
                                "then_body": [{"kind": "print", "expr": {"kind": "var", "name": "greeting"}}],
                                "else_body": [{"kind": "print", "expr": {"kind": "string", "value": "disabled"}}],
                            },
                        ],
                    },
                    {"kind": "print_many", "texts": ["hello, world!"]},
                    "hello, world!",
                ),
            ]

            for filename, expected_ast, expected_artifact, expected_output in cases:
                with self.subTest(filename=filename):
                    source = (root / "examples" / filename).read_text(encoding="utf-8")
                    ast = run_subset_program(frontend, entry="parse", args=[source])
                    checked = run_subset_program(frontend, entry="check", args=[source])
                    lowered = run_subset_program(frontend, entry="lower", args=[source])
                    compiled = run_subset_program(frontend, entry="compile", args=[source])
                    self.assertEqual(json.loads(ast), expected_ast)
                    self.assertEqual(checked, "ok")
                    self.assertEqual(json.loads(lowered), expected_artifact)
                    self.assertEqual(json.loads(compiled), expected_artifact)
                    fragment = capir_fragment_from_artifact(compiled)
                    self.assertEqual(execute_capir_fragment(fragment).output, expected_output)
        finally:
            subset_module.BUILTINS.clear()
            subset_module.BUILTINS.update(saved_builtins)

    def test_selfhost_frontend_supports_if_statement_blocks(self):
        root = Path(__file__).resolve().parents[1]
        frontend = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        source = (root / "examples" / "hello_if_stmt.ksrc").read_text(encoding="utf-8")
        ast = run_subset_program(frontend, entry="parse", args=[source])
        lowered = run_subset_program(frontend, entry="lower", args=[source])
        self.assertEqual(
            json.loads(ast),
            {
                "kind": "program",
                "functions": [],
                "statements": [
                    {
                        "kind": "let",
                        "name": "greeting",
                        "expr": {
                            "kind": "concat",
                            "left": {"kind": "string", "value": "hello, "},
                            "right": {"kind": "string", "value": "world!"},
                        },
                    },
                    {
                        "kind": "let",
                        "name": "enabled",
                        "expr": {
                            "kind": "eq",
                            "left": {"kind": "var", "name": "greeting"},
                            "right": {"kind": "string", "value": "hello, world!"},
                        },
                    },
                    {
                        "kind": "if_stmt",
                        "condition": {"kind": "var", "name": "enabled"},
                        "then_body": [
                            {"kind": "print", "expr": {"kind": "var", "name": "greeting"}},
                        ],
                        "else_body": [
                            {"kind": "print", "expr": {"kind": "string", "value": "disabled"}},
                        ],
                    },
                ],
            },
        )
        self.assertEqual(json.loads(lowered), {"kind": "print_many", "texts": ["hello, world!"]})

    def test_selfhost_frontend_supports_function_and_call(self):
        root = Path(__file__).resolve().parents[1]
        frontend = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        source = (root / "examples" / "hello_fn.ksrc").read_text(encoding="utf-8")
        ast = run_subset_program(frontend, entry="parse", args=[source])
        lowered = run_subset_program(frontend, entry="lower", args=[source])
        self.assertEqual(
            json.loads(ast),
            {
                "kind": "program",
                "functions": [
                    {
                        "kind": "fn",
                        "name": "emit_greeting",
                        "params": [],
                        "body": [
                            {
                                "kind": "let",
                                "name": "greeting",
                                "expr": {
                                    "kind": "concat",
                                    "left": {"kind": "string", "value": "hello, "},
                                    "right": {"kind": "string", "value": "world!"},
                                },
                            },
                            {"kind": "print", "expr": {"kind": "var", "name": "greeting"}},
                        ],
                    }
                ],
                "statements": [
                    {"kind": "call", "name": "emit_greeting", "args": []},
                ],
            },
        )
        self.assertEqual(json.loads(lowered), {"kind": "print_many", "texts": ["hello, world!"]})

    def test_selfhost_frontend_supports_single_argument_function_call(self):
        root = Path(__file__).resolve().parents[1]
        frontend = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        source = (root / "examples" / "hello_arg_fn.ksrc").read_text(encoding="utf-8")
        ast = run_subset_program(frontend, entry="parse", args=[source])
        lowered = run_subset_program(frontend, entry="lower", args=[source])
        self.assertEqual(
            json.loads(ast),
            {
                "kind": "program",
                "functions": [
                    {
                        "kind": "fn",
                        "name": "emit_suffix",
                        "params": ["name"],
                        "body": [
                            {
                                "kind": "print",
                                "expr": {
                                    "kind": "concat",
                                    "left": {"kind": "var", "name": "name"},
                                    "right": {"kind": "string", "value": "!"},
                                },
                            }
                        ],
                    }
                ],
                "statements": [
                    {
                        "kind": "call",
                        "name": "emit_suffix",
                        "args": [{"kind": "string", "value": "hello, world"}],
                    },
                ],
            },
        )
        self.assertEqual(json.loads(lowered), {"kind": "print_many", "texts": ["hello, world!"]})

    def test_selfhost_frontend_selfhosts_simple_single_argument_function_call(self):
        root = Path(__file__).resolve().parents[1]
        frontend = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        source = (root / "examples" / "hello_arg_fn.ksrc").read_text(encoding="utf-8")
        ast = run_subset_program(frontend, entry="parse", args=[source])
        self.assertEqual(
            json.loads(ast),
            {
                "kind": "program",
                "functions": [
                    {
                        "kind": "fn",
                        "name": "emit_suffix",
                        "params": ["name"],
                        "body": [
                            {
                                "kind": "print",
                                "expr": {
                                    "kind": "concat",
                                    "left": {"kind": "var", "name": "name"},
                                    "right": {"kind": "string", "value": "!"},
                                },
                            }
                        ],
                    }
                ],
                "statements": [
                    {
                        "kind": "call",
                        "name": "emit_suffix",
                        "args": [{"kind": "string", "value": "hello, world"}],
                    }
                ],
            },
        )

    def test_selfhost_frontend_checks_invalid_source(self):
        root = Path(__file__).resolve().parents[1]
        frontend = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        invalid = (root / "examples" / "hello_invalid.ksrc").read_text(encoding="utf-8")
        parsed = run_subset_program(frontend, entry="parse", args=[invalid])
        checked = run_subset_program(frontend, entry="check", args=[invalid])
        lowered = run_subset_program(frontend, entry="lower", args=[invalid])
        self.assertEqual(parsed, "error: unsupported source")
        self.assertEqual(checked, "error: unsupported source")
        self.assertEqual(lowered, "error: unsupported source")

    def test_selfhost_frontend_no_longer_uses_python_parse_check_lower_builtins_for_current_examples(self):
        root = Path(__file__).resolve().parents[1]
        frontend = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        example_names = [
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
        ]
        saved_builtins = dict(subset_module.BUILTINS)
        try:
            subset_module.BUILTINS.pop("parse_print_program", None)
            subset_module.BUILTINS.pop("validate_program_ast", None)
            subset_module.BUILTINS.pop("lower_program_artifact", None)
            for example_name in example_names:
                source = (root / "examples" / example_name).read_text(encoding="utf-8")
                parsed = run_subset_program(frontend, entry="parse", args=[source])
                checked = run_subset_program(frontend, entry="check", args=[source])
                lowered = run_subset_program(frontend, entry="lower", args=[source])
                compiled = run_subset_program(frontend, entry="compile", args=[source])
                self.assertFalse(parsed.startswith("error:"), example_name)
                self.assertEqual(checked, "ok", example_name)
                self.assertFalse(lowered.startswith("error:"), example_name)
                self.assertEqual(compiled, lowered, example_name)
        finally:
            subset_module.BUILTINS.clear()
            subset_module.BUILTINS.update(saved_builtins)

    def test_selfhost_frontend_source_no_longer_references_legacy_parse_check_lower_builtins(self):
        root = Path(__file__).resolve().parents[1]
        frontend = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        self.assertNotIn("parse_print_program", frontend)
        self.assertNotIn("validate_program_ast", frontend)
        self.assertNotIn("lower_program_artifact", frontend)

    def test_legacy_parse_check_lower_builtins_are_not_registered(self):
        self.assertNotIn("parse_print_program", subset_module.BUILTINS)
        self.assertNotIn("validate_program_ast", subset_module.BUILTINS)
        self.assertNotIn("lower_program_artifact", subset_module.BUILTINS)

    def test_inspect_capir_artifact_returns_serialized_view(self):
        artifact = json.dumps({"kind": "print_many", "texts": ["hello", "world"]})
        payload = inspect_capir_artifact(artifact)
        self.assertEqual(payload["effect"], "print")
        self.assertEqual(payload["ops"], [{"text": "hello"}, {"text": "world"}])
        self.assertEqual(payload["serialized"], 'print "hello"\nprint "world"\n')

    def test_execute_and_inspect_capir_artifact_returns_capir_and_output(self):
        artifact = json.dumps({"kind": "print_many", "texts": ["hello", "world"]})
        result = execute_and_inspect_capir_artifact(artifact)
        self.assertEqual(result.capir["serialized"], 'print "hello"\nprint "world"\n')
        self.assertEqual(result.output, "hello\nworld")

    def test_kir_print_program_scaffold_roundtrips(self):
        artifact = json.dumps({"kind": "print_many", "texts": ["hello", "world"]})
        program = kir_program_from_print_artifact(parse_artifact_v1(artifact))
        self.assertEqual(inspect_kir_artifact(program)["ops"], [{"text": "hello"}, {"text": "world"}])
        self.assertEqual(serialize_kir_program_v0(program), '{"kind":"kir","effect":"print","ops":[{"text":"hello"},{"text":"world"}]}')

    def test_compile_source_v1_returns_typed_pipeline_result(self):
        root = Path(__file__).resolve().parents[1]
        frontend = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        source = (root / "examples" / "hello_arg_fn.ksrc").read_text(encoding="utf-8")
        compiled = compile_source_v1(frontend, source)
        self.assertEqual(compiled.check.ok, True)
        self.assertEqual(compiled.check.effects.program_effects, ["print"])
        self.assertEqual(compiled.check.effects.function_effects["emit_suffix"], ["print"])
        self.assertEqual(compiled.stdout, "hello, world!")
        self.assertEqual(compiled.compile_artifact.texts, ["hello, world!"])
        self.assertEqual(compiled.lower.artifact.texts, ["hello, world!"])
        self.assertEqual(compiled.lower.kir.functions[0].name, "emit_suffix")
        self.assertEqual(inspect_kir_artifact(compiled.lower.kir)["instructions"][0]["op"], "call")
        self.assertEqual(compiled.parse.surface_ast.functions[0].name, "emit_suffix")

    def test_compile_source_v1_does_not_depend_on_subset_eval(self):
        root = Path(__file__).resolve().parents[1]
        frontend = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        source = (root / "examples" / "hello_arg_fn.ksrc").read_text(encoding="utf-8")

        with patch("kagi.subset_eval.run_subset_program", side_effect=AssertionError("subset_eval should not be used")):
            compiled = compile_source_v1(frontend, source)

        self.assertEqual(compiled.stdout, "hello, world!")
        self.assertEqual(compiled.lower.artifact.texts, ["hello, world!"])
        self.assertEqual(compiled.parse.surface_ast.functions[0].name, "emit_suffix")

    def test_compile_source_v1_does_not_depend_on_python_hir_lowering(self):
        root = Path(__file__).resolve().parents[1]
        frontend = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        source = (root / "examples" / "hello_arg_fn.ksrc").read_text(encoding="utf-8")

        with patch("kagi.compile_result.lower_surface_program_to_hir_v1", side_effect=AssertionError("python hir lowering should not be used"), create=True):
            compiled = compile_source_v1(frontend, source)

        self.assertEqual(compiled.stdout, "hello, world!")
        self.assertEqual(compiled.lower.hir.functions[0].name, "emit_suffix")

    def test_compile_source_v1_does_not_depend_on_subset_kir_fallback(self):
        root = Path(__file__).resolve().parents[1]
        frontend = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        source = (root / "examples" / "hello_arg_fn.ksrc").read_text(encoding="utf-8")

        with patch("kagi.selfhost_runtime.execute_subset_entry_via_kir_v0", side_effect=AssertionError("subset fallback should not be used")):
            compiled = compile_source_v1(frontend, source)

        self.assertEqual(compiled.stdout, "hello, world!")
        self.assertEqual(compiled.lower.kir.functions[0].name, "emit_suffix")

    def test_compile_source_v1_uses_canonical_frontend_kir_image_without_subset_parser(self):
        root = Path(__file__).resolve().parents[1]
        frontend = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        source = (root / "examples" / "hello_arg_fn.ksrc").read_text(encoding="utf-8")

        with patch("kagi.selfhost_runtime.execute_subset_entry_via_kir_v0", side_effect=AssertionError("subset fallback should not be used")):
            with patch("kagi.selfhost_runtime.parse_subset_program", side_effect=AssertionError("subset parser should not be used")):
                with patch("kagi.selfhost_runtime.lower_subset_program_to_kir_v0", side_effect=AssertionError("subset kir lowering should not be used")):
                    compiled = compile_source_v1(frontend, source)

        self.assertEqual(compiled.stdout, "hello, world!")
        self.assertEqual(compiled.lower.kir.functions[0].name, "emit_suffix")

    def test_compile_source_v1_does_not_depend_on_python_static_passes(self):
        root = Path(__file__).resolve().parents[1]
        frontend = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        source = (root / "examples" / "hello_arg_fn.ksrc").read_text(encoding="utf-8")

        with patch("kagi.compile_result.resolve_hir_program_v1", side_effect=AssertionError("python resolve should not be used"), create=True):
            with patch("kagi.compile_result.typecheck_program_v1", side_effect=AssertionError("python typecheck should not be used"), create=True):
                with patch("kagi.compile_result.infer_effects_v1", side_effect=AssertionError("python effects should not be used"), create=True):
                    compiled = compile_source_v1(frontend, source)

        self.assertEqual(compiled.stdout, "hello, world!")
        self.assertEqual(compiled.check.effects.function_effects["emit_suffix"], ["print"])

    def test_parse_selfhost_pipeline_bundle_v1_returns_typed_bundle(self):
        bundle = parse_selfhost_pipeline_bundle_v1(
            '{"kind":"pipeline_bundle","ast":{"kind":"program","functions":[],"statements":[{"kind":"print","expr":{"kind":"string","value":"hello"}}]},"hir":{"kind":"hir_program","functions":[],"statements":[{"kind":"print","expr":{"kind":"string","value":"hello"}}]},"kir":{"kind":"kir","effect":"print","ops":[{"text":"hello"}]},"analysis":{"kind":"analysis_v1","function_arities":{},"effects":{"program":["print"],"functions":{}}},"check":"ok","artifact":{"kind":"print_many","texts":["hello"]},"compile":{"kind":"print_many","texts":["hello"]}}'
        )
        self.assertEqual(bundle.raw_check, "ok")
        self.assertEqual(bundle.surface_ast.statements[0].expr.value, "hello")
        self.assertEqual(bundle.hir.statements[0].expr.value, "hello")
        self.assertEqual(bundle.kir.instructions[0].text, "hello")
        self.assertEqual(bundle.analysis.program_effects, ["print"])
        self.assertEqual(bundle.artifact.texts, ["hello"])
        self.assertEqual(bundle.compile_artifact.texts, ["hello"])

    def test_parse_selfhost_pipeline_bundle_v1_rejects_invalid_kind(self):
        with self.assertRaises(DiagnosticError):
            parse_selfhost_pipeline_bundle_v1('{"kind":"other"}')

    def test_parse_selfhost_pipeline_bundle_v1_rejects_missing_ast(self):
        with self.assertRaises(DiagnosticError):
            parse_selfhost_pipeline_bundle_v1(
                '{"kind":"pipeline_bundle","hir":{"kind":"hir_program","functions":[],"statements":[{"kind":"print","expr":{"kind":"string","value":"hello"}}]},"kir":{"kind":"kir","effect":"print","ops":[{"text":"hello"}]},"analysis":{"kind":"analysis_v1","function_arities":{},"effects":{"program":["print"],"functions":{}}},"check":"ok","artifact":{"kind":"print_many","texts":["hello"]},"compile":{"kind":"print_many","texts":["hello"]}}'
            )

    def test_parse_selfhost_pipeline_bundle_v1_rejects_missing_artifact(self):
        with self.assertRaises(DiagnosticError):
            parse_selfhost_pipeline_bundle_v1(
                '{"kind":"pipeline_bundle","ast":{"kind":"program","functions":[],"statements":[]},"hir":{"kind":"hir_program","functions":[],"statements":[]},"kir":{"kind":"kir","effect":"print","ops":[]},"analysis":{"kind":"analysis_v1","function_arities":{},"effects":{"program":["pure"],"functions":{}}},"check":"ok","compile":{"kind":"print_many","texts":["hello"]}}'
            )

    def test_parse_selfhost_pipeline_bundle_v1_rejects_non_ok_check(self):
        with self.assertRaises(DiagnosticError):
            parse_selfhost_pipeline_bundle_v1(
                '{"kind":"pipeline_bundle","ast":{"kind":"program","functions":[],"statements":[]},"hir":{"kind":"hir_program","functions":[],"statements":[]},"kir":{"kind":"kir","effect":"print","ops":[]},"analysis":{"kind":"analysis_v1","function_arities":{},"effects":{"program":["pure"],"functions":{}}},"check":"error","artifact":{"kind":"print_many","texts":["hello"]},"compile":{"kind":"print_many","texts":["hello"]}}'
            )

    def test_parse_selfhost_pipeline_bundle_v1_rejects_mismatched_compile(self):
        with self.assertRaises(DiagnosticError):
            parse_selfhost_pipeline_bundle_v1(
                '{"kind":"pipeline_bundle","ast":{"kind":"program","functions":[],"statements":[]},"hir":{"kind":"hir_program","functions":[],"statements":[]},"kir":{"kind":"kir","effect":"print","ops":[]},"analysis":{"kind":"analysis_v1","function_arities":{},"effects":{"program":["pure"],"functions":{}}},"check":"ok","artifact":{"kind":"print_many","texts":["hello"]},"compile":{"kind":"print_many","texts":["world"]}}'
            )

    def test_selfhost_pipeline_bundle_v1_to_json_roundtrips(self):
        raw = '{"kind":"pipeline_bundle","ast":{"kind":"program","functions":[],"statements":[{"kind":"print","expr":{"kind":"string","value":"hello"}}]},"hir":{"kind":"hir_program","functions":[],"statements":[{"kind":"print","expr":{"kind":"string","value":"hello"}}]},"kir":{"kind":"kir","effect":"print","ops":[{"text":"hello"}]},"analysis":{"kind":"analysis_v1","function_arities":{},"effects":{"program":["print"],"functions":{}}},"check":"ok","artifact":{"kind":"print_many","texts":["hello"]},"compile":{"kind":"print_many","texts":["hello"]}}'
        bundle = parse_selfhost_pipeline_bundle_v1(raw)
        self.assertEqual(json.loads(selfhost_pipeline_bundle_v1_to_json(bundle)), json.loads(raw))

    def test_package_exports_artifact_abi_helpers(self):
        self.assertTrue(hasattr(kagi, "execute_capir_artifact"))
        self.assertTrue(hasattr(kagi, "inspect_capir_artifact"))
        self.assertTrue(hasattr(kagi, "compile_source_v1"))
        self.assertTrue(hasattr(kagi, "PrintArtifactV1"))
        self.assertTrue(hasattr(kagi, "SurfaceProgramV1"))
        self.assertTrue(hasattr(kagi, "HIRProgramV1"))
        self.assertFalse(hasattr(kagi, "parse_tiny_program_ast_json"))
        self.assertIsNone(importlib.util.find_spec("kagi.selfhost"))

    def test_cli_selfhost_run_outputs_hello_world(self):
        root = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "kagi.cli",
                "selfhost-run",
                "--json",
                str(root / "examples" / "selfhost_frontend.ks"),
                str(root / "examples" / "hello.ksrc"),
            ],
            cwd=root,
            env={"PYTHONPATH": str(root / "src")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        payload = __import__("json").loads(proc.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["entry"], "pipeline")
        self.assertEqual(payload["value"], "hello, world!")
        self.assertEqual(payload["kir"]["effect"], "print")
        self.assertEqual(payload["kir"]["ops"], [{"text": "hello, world!"}])
        self.assertEqual(
            json.loads(payload["ast"]),
            {
                "kind": "program",
                "functions": [],
                "statements": [
                    {
                        "kind": "print",
                        "expr": {
                            "kind": "string",
                            "value": "hello, world!",
                        },
                    }
                ],
            },
        )

    def test_cli_selfhost_run_outputs_let_expression(self):
        root = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "kagi.cli",
                "selfhost-run",
                "--json",
                str(root / "examples" / "selfhost_frontend.ks"),
                str(root / "examples" / "hello_let.ksrc"),
            ],
            cwd=root,
            env={"PYTHONPATH": str(root / "src")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        payload = __import__("json").loads(proc.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["value"], "hello, world!")
        self.assertEqual(payload["artifact"], '{"kind":"print_many","texts":["hello, world!"]}')
        self.assertEqual(payload["capir"]["serialized"], 'print "hello, world!"\n')

    def test_cli_selfhost_run_outputs_simple_let_string_expression(self):
        root = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "kagi.cli",
                "selfhost-run",
                "--json",
                str(root / "examples" / "selfhost_frontend.ks"),
                str(root / "examples" / "hello_let_string.ksrc"),
            ],
            cwd=root,
            env={"PYTHONPATH": str(root / "src")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        payload = __import__("json").loads(proc.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["value"], "hello, world!")
        self.assertEqual(payload["artifact"], '{"kind":"print_many","texts":["hello, world!"]}')

    def test_cli_selfhost_check_outputs_ok_for_selfhosted_single_print(self):
        root = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "kagi.cli",
                "selfhost-check",
                "--json",
                str(root / "examples" / "selfhost_frontend.ks"),
                str(root / "examples" / "hello.ksrc"),
            ],
            cwd=root,
            env={"PYTHONPATH": str(root / "src")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        payload = __import__("json").loads(proc.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["entry"], "pipeline")
        self.assertEqual(payload["value"], "ok")
        self.assertEqual(payload["effects"]["program"], ["print"])

    def test_cli_selfhost_check_outputs_ok_for_selfhosted_print_concat(self):
        root = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "kagi.cli",
                "selfhost-check",
                "--json",
                str(root / "examples" / "selfhost_frontend.ks"),
                str(root / "examples" / "hello_print_concat.ksrc"),
            ],
            cwd=root,
            env={"PYTHONPATH": str(root / "src")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        payload = __import__("json").loads(proc.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["value"], "ok")

    def test_cli_selfhost_check_outputs_ok_for_selfhosted_let_print(self):
        root = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "kagi.cli",
                "selfhost-check",
                "--json",
                str(root / "examples" / "selfhost_frontend.ks"),
                str(root / "examples" / "hello_let_string.ksrc"),
            ],
            cwd=root,
            env={"PYTHONPATH": str(root / "src")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        payload = __import__("json").loads(proc.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["value"], "ok")

    def test_cli_selfhost_check_outputs_ok_for_selfhosted_let_concat_print(self):
        root = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "kagi.cli",
                "selfhost-check",
                "--json",
                str(root / "examples" / "selfhost_frontend.ks"),
                str(root / "examples" / "hello_let_concat.ksrc"),
            ],
            cwd=root,
            env={"PYTHONPATH": str(root / "src")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        payload = __import__("json").loads(proc.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["value"], "ok")

    def test_cli_selfhost_check_outputs_ok_for_selfhosted_function_call(self):
        root = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "kagi.cli",
                "selfhost-check",
                "--json",
                str(root / "examples" / "selfhost_frontend.ks"),
                str(root / "examples" / "hello_arg_fn.ksrc"),
            ],
            cwd=root,
            env={"PYTHONPATH": str(root / "src")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        payload = __import__("json").loads(proc.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["value"], "ok")

    def test_cli_selfhost_emit_outputs_selfhosted_single_print_artifact(self):
        root = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "kagi.cli",
                "selfhost-emit",
                "--json",
                str(root / "examples" / "selfhost_frontend.ks"),
                str(root / "examples" / "hello.ksrc"),
            ],
            cwd=root,
            env={"PYTHONPATH": str(root / "src")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        payload = __import__("json").loads(proc.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["artifact"], '{"kind":"print_many","texts":["hello, world!"]}')

    def test_cli_selfhost_emit_outputs_selfhosted_print_concat_artifact(self):
        root = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "kagi.cli",
                "selfhost-emit",
                "--json",
                str(root / "examples" / "selfhost_frontend.ks"),
                str(root / "examples" / "hello_print_concat.ksrc"),
            ],
            cwd=root,
            env={"PYTHONPATH": str(root / "src")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        payload = __import__("json").loads(proc.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["artifact"], '{"kind":"print_many","texts":["hello, world!"]}')

    def test_cli_selfhost_emit_outputs_selfhosted_let_print_artifact(self):
        root = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "kagi.cli",
                "selfhost-emit",
                "--json",
                str(root / "examples" / "selfhost_frontend.ks"),
                str(root / "examples" / "hello_let_string.ksrc"),
            ],
            cwd=root,
            env={"PYTHONPATH": str(root / "src")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        payload = __import__("json").loads(proc.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["artifact"], '{"kind":"print_many","texts":["hello, world!"]}')

    def test_cli_selfhost_emit_outputs_selfhosted_let_concat_artifact(self):
        root = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "kagi.cli",
                "selfhost-emit",
                "--json",
                str(root / "examples" / "selfhost_frontend.ks"),
                str(root / "examples" / "hello_let_concat.ksrc"),
            ],
            cwd=root,
            env={"PYTHONPATH": str(root / "src")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        payload = __import__("json").loads(proc.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["artifact"], '{"kind":"print_many","texts":["hello, world!"]}')

    def test_cli_selfhost_emit_outputs_selfhosted_function_call_artifact(self):
        root = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "kagi.cli",
                "selfhost-emit",
                "--json",
                str(root / "examples" / "selfhost_frontend.ks"),
                str(root / "examples" / "hello_arg_fn.ksrc"),
            ],
            cwd=root,
            env={"PYTHONPATH": str(root / "src")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        payload = __import__("json").loads(proc.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["artifact"], '{"kind":"print_many","texts":["hello, world!"]}')

    def test_cli_selfhost_run_outputs_function_call(self):
        root = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "kagi.cli",
                "selfhost-run",
                "--json",
                str(root / "examples" / "selfhost_frontend.ks"),
                str(root / "examples" / "hello_fn.ksrc"),
            ],
            cwd=root,
            env={"PYTHONPATH": str(root / "src")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        payload = __import__("json").loads(proc.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["value"], "hello, world!")
        self.assertEqual(payload["artifact"], '{"kind":"print_many","texts":["hello, world!"]}')
        self.assertEqual(payload["capir"]["serialized"], 'print "hello, world!"\n')

    def test_cli_selfhost_run_outputs_single_argument_function_call(self):
        root = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "kagi.cli",
                "selfhost-run",
                "--json",
                str(root / "examples" / "selfhost_frontend.ks"),
                str(root / "examples" / "hello_arg_fn.ksrc"),
            ],
            cwd=root,
            env={"PYTHONPATH": str(root / "src")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        payload = __import__("json").loads(proc.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["value"], "hello, world!")
        self.assertEqual(payload["artifact"], '{"kind":"print_many","texts":["hello, world!"]}')
        self.assertEqual(payload["capir"]["serialized"], 'print "hello, world!"\n')

    def test_cli_selfhost_run_outputs_if_expression(self):
        root = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "kagi.cli",
                "selfhost-run",
                "--json",
                str(root / "examples" / "selfhost_frontend.ks"),
                str(root / "examples" / "hello_if.ksrc"),
            ],
            cwd=root,
            env={"PYTHONPATH": str(root / "src")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        payload = __import__("json").loads(proc.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["value"], "hello, world!")
        self.assertEqual(payload["artifact"], '{"kind":"print_many","texts":["hello, world!"]}')
        self.assertEqual(payload["capir"]["serialized"], 'print "hello, world!"\n')

    def test_cli_selfhost_run_outputs_if_statement(self):
        root = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "kagi.cli",
                "selfhost-run",
                "--json",
                str(root / "examples" / "selfhost_frontend.ks"),
                str(root / "examples" / "hello_if_stmt.ksrc"),
            ],
            cwd=root,
            env={"PYTHONPATH": str(root / "src")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        payload = __import__("json").loads(proc.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["value"], "hello, world!")
        self.assertEqual(payload["artifact"], '{"kind":"print_many","texts":["hello, world!"]}')
        self.assertEqual(payload["capir"]["serialized"], 'print "hello, world!"\n')

    def test_cli_selfhost_run_outputs_multiple_lines(self):
        root = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "kagi.cli",
                "selfhost-run",
                "--json",
                str(root / "examples" / "selfhost_frontend.ks"),
                str(root / "examples" / "hello_twice.ksrc"),
            ],
            cwd=root,
            env={"PYTHONPATH": str(root / "src")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        payload = __import__("json").loads(proc.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["value"], "hello\nworld")
        self.assertEqual(payload["artifact"], '{"kind":"print_many","texts":["hello","world"]}')
        self.assertEqual(payload["capir"]["serialized"], 'print "hello"\nprint "world"\n')

    def test_cli_selfhost_run_outputs_concat_expression(self):
        root = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "kagi.cli",
                "selfhost-run",
                "--json",
                str(root / "examples" / "selfhost_frontend.ks"),
                str(root / "examples" / "hello_concat.ksrc"),
            ],
            cwd=root,
            env={"PYTHONPATH": str(root / "src")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        payload = __import__("json").loads(proc.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["value"], "hello, world!")

    def test_cli_selfhost_run_writes_plain_stdout_without_json(self):
        root = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "kagi.cli",
                "selfhost-run",
                str(root / "examples" / "selfhost_frontend.ks"),
                str(root / "examples" / "hello_concat.ksrc"),
            ],
            cwd=root,
            env={"PYTHONPATH": str(root / "src")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "hello, world!\n")
        self.assertEqual(proc.stderr, "")

    def test_cli_selfhost_run_main_path_does_not_call_python_kir_executor(self):
        root = Path(__file__).resolve().parents[1]
        stdout = io.StringIO()
        argv = [
            "kagi",
            "selfhost-run",
            str(root / "examples" / "selfhost_frontend.ks"),
            str(root / "examples" / "hello_arg_fn.ksrc"),
        ]

        with patch.object(sys, "argv", argv):
            with patch.object(
                cli_module,
                "execute_kir_program",
                side_effect=AssertionError("python kir executor should not be used by selfhost-run"),
                create=True,
            ):
                with redirect_stdout(stdout):
                    cli_module.main()

        self.assertEqual(stdout.getvalue(), "hello, world!\n")

    def test_cli_canonical_selfhost_commands_do_not_use_typed_compile_helpers(self):
        root = Path(__file__).resolve().parents[1]
        cases = (
            (
                [
                    "kagi",
                    "selfhost-run",
                    str(root / "examples" / "selfhost_frontend.ks"),
                    str(root / "examples" / "hello_arg_fn.ksrc"),
                ],
                lambda text: self.assertEqual(text, "hello, world!\n"),
            ),
            (
                [
                    "kagi",
                    "selfhost-run",
                    "--json",
                    str(root / "examples" / "selfhost_frontend.ks"),
                    str(root / "examples" / "hello.ksrc"),
                ],
                lambda text: self.assertEqual(json.loads(text)["value"], "hello, world!"),
            ),
            (
                [
                    "kagi",
                    "selfhost-check",
                    "--json",
                    str(root / "examples" / "selfhost_frontend.ks"),
                    str(root / "examples" / "hello_if.ksrc"),
                ],
                lambda text: self.assertEqual(json.loads(text)["effects"]["program"], ["print"]),
            ),
            (
                [
                    "kagi",
                    "selfhost-emit",
                    "--json",
                    str(root / "examples" / "selfhost_frontend.ks"),
                    str(root / "examples" / "hello_let.ksrc"),
                ],
                lambda text: self.assertEqual(json.loads(text)["artifact"], '{"kind":"print_many","texts":["hello, world!"]}'),
            ),
            (
                [
                    "kagi",
                    "selfhost-capir",
                    "--json",
                    str(root / "examples" / "selfhost_frontend.ks"),
                    str(root / "examples" / "hello_concat.ksrc"),
                ],
                lambda text: self.assertEqual(json.loads(text)["capir"]["serialized"], 'print "hello, world!"\n'),
            ),
        )

        for argv, assertion in cases:
            with self.subTest(command=argv[1], source=argv[-1]):
                stdout = io.StringIO()
                with patch.object(sys, "argv", argv):
                    with ExitStack() as stack:
                        stack.enter_context(
                            patch.object(
                                cli_module,
                                "compile_source_v1",
                                side_effect=AssertionError("typed compile path should not be used by canonical cli path"),
                                create=True,
                            )
                        )
                        stack.enter_context(
                            patch.object(
                                cli_module,
                                "inspect_hir_program_v1",
                                side_effect=AssertionError("typed hir inspect should not be used by canonical cli path"),
                                create=True,
                            )
                        )
                        stack.enter_context(
                            patch.object(
                                cli_module,
                                "inspect_kir_artifact",
                                side_effect=AssertionError("typed kir inspect should not be used by canonical cli path"),
                                create=True,
                            )
                        )
                        stack.enter_context(
                            patch.object(
                                cli_module,
                                "inspect_capir_artifact",
                                side_effect=AssertionError("typed capir inspect should not be used by canonical cli path"),
                                create=True,
                            )
                        )
                        stack.enter_context(
                            patch.object(
                                cli_module,
                                "artifact_v1_to_json",
                                side_effect=AssertionError("typed artifact encode should not be used by canonical cli path"),
                                create=True,
                            )
                        )
                        with redirect_stdout(stdout):
                            cli_module.main()
                assertion(stdout.getvalue())

    def test_cli_selfhost_check_and_emit(self):
        root = Path(__file__).resolve().parents[1]
        parse_proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "kagi.cli",
                "selfhost-parse",
                "--json",
                str(root / "examples" / "selfhost_frontend.ks"),
                str(root / "examples" / "hello.ksrc"),
            ],
            cwd=root,
            env={"PYTHONPATH": str(root / "src")},
            capture_output=True,
            text=True,
            check=False,
        )
        check_proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "kagi.cli",
                "selfhost-check",
                "--json",
                str(root / "examples" / "selfhost_frontend.ks"),
                str(root / "examples" / "hello.ksrc"),
            ],
            cwd=root,
            env={"PYTHONPATH": str(root / "src")},
            capture_output=True,
            text=True,
            check=False,
        )
        emit_proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "kagi.cli",
                "selfhost-emit",
                "--json",
                str(root / "examples" / "selfhost_frontend.ks"),
                str(root / "examples" / "hello.ksrc"),
            ],
            cwd=root,
            env={"PYTHONPATH": str(root / "src")},
            capture_output=True,
            text=True,
            check=False,
        )
        invalid_proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "kagi.cli",
                "selfhost-check",
                "--json",
                str(root / "examples" / "selfhost_frontend.ks"),
                str(root / "examples" / "hello_invalid.ksrc"),
            ],
            cwd=root,
            env={"PYTHONPATH": str(root / "src")},
            capture_output=True,
            text=True,
            check=False,
        )
        capir_proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "kagi.cli",
                "selfhost-capir",
                "--json",
                str(root / "examples" / "selfhost_frontend.ks"),
                str(root / "examples" / "hello.ksrc"),
            ],
            cwd=root,
            env={"PYTHONPATH": str(root / "src")},
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(parse_proc.returncode, 0)
        self.assertEqual(check_proc.returncode, 0)
        self.assertEqual(emit_proc.returncode, 0)
        self.assertEqual(capir_proc.returncode, 0)
        self.assertEqual(invalid_proc.returncode, 1)

        parse_payload = __import__("json").loads(parse_proc.stdout)
        check_payload = __import__("json").loads(check_proc.stdout)
        emit_payload = __import__("json").loads(emit_proc.stdout)
        capir_payload = __import__("json").loads(capir_proc.stdout)
        invalid_payload = __import__("json").loads(invalid_proc.stdout)

        self.assertEqual(parse_payload["ast"], '{"kind":"program","functions":[],"statements":[{"kind":"print","expr":{"kind":"string","value":"hello, world!"}}]}')
        self.assertEqual(check_payload["ast"], '{"kind":"program","functions":[],"statements":[{"kind":"print","expr":{"kind":"string","value":"hello, world!"}}]}')
        self.assertEqual(emit_payload["ast"], '{"kind":"program","functions":[],"statements":[{"kind":"print","expr":{"kind":"string","value":"hello, world!"}}]}')
        self.assertEqual(check_payload["entry"], "pipeline")
        self.assertEqual(emit_payload["entry"], "pipeline")
        self.assertEqual(capir_payload["entry"], "pipeline")
        self.assertEqual(check_payload["value"], "ok")
        self.assertEqual(emit_payload["artifact"], '{"kind":"print_many","texts":["hello, world!"]}')
        self.assertEqual(capir_payload["capir"]["serialized"], 'print "hello, world!"\n')
        self.assertFalse(invalid_payload["ok"])
        self.assertEqual(invalid_payload["value"], "error: unsupported source")


if __name__ == "__main__":
    unittest.main()
