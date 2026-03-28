import unittest
from pathlib import Path
import subprocess
import sys

from kagi.diagnostics import DiagnosticError
from kagi.frontend import execute_bootstrap_program, parse_bootstrap_program, parse_core_program
from kagi.ir import serialize_program_ir
from kagi.subset import parse_subset_program, run_subset_program
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

    def test_selfhost_frontend_emits_hello_world(self):
        root = Path(__file__).resolve().parents[1]
        frontend = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        source = (root / "examples" / "hello.ksrc").read_text(encoding="utf-8")
        lowered = run_subset_program(frontend, entry="lower", args=[source])
        compiled = run_subset_program(frontend, entry="compile", args=[source])
        self.assertEqual(lowered, "emit:hello, world!")
        self.assertEqual(compiled, "emit:hello, world!")

    def test_selfhost_frontend_checks_invalid_source(self):
        root = Path(__file__).resolve().parents[1]
        frontend = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        invalid = (root / "examples" / "hello_invalid.ksrc").read_text(encoding="utf-8")
        checked = run_subset_program(frontend, entry="check", args=[invalid])
        lowered = run_subset_program(frontend, entry="lower", args=[invalid])
        self.assertEqual(checked, "error: expected quoted string")
        self.assertEqual(lowered, "error: expected quoted string")

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
        self.assertEqual(payload["value"], "emit:hello, world!")

    def test_cli_selfhost_check_and_emit(self):
        root = Path(__file__).resolve().parents[1]
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

        self.assertEqual(check_proc.returncode, 0)
        self.assertEqual(emit_proc.returncode, 0)
        self.assertEqual(invalid_proc.returncode, 1)

        check_payload = __import__("json").loads(check_proc.stdout)
        emit_payload = __import__("json").loads(emit_proc.stdout)
        invalid_payload = __import__("json").loads(invalid_proc.stdout)

        self.assertEqual(check_payload["value"], "ok")
        self.assertEqual(emit_payload["artifact"], "emit:hello, world!")
        self.assertFalse(invalid_payload["ok"])
        self.assertEqual(invalid_payload["value"], "error: expected quoted string")


if __name__ == "__main__":
    unittest.main()
