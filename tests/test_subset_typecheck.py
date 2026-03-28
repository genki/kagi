from __future__ import annotations

import unittest

from kagi.diagnostics import DiagnosticError
from kagi.subset import parse_subset_program, run_subset_program, typecheck_subset_program_v0


class SubsetTypecheckTest(unittest.TestCase):
    def test_typed_function_signature_parses_and_runs(self):
        source = """
        fn greet(name: string) -> string {
            return name;
        }
        """
        program = parse_subset_program(source)
        self.assertEqual(program.functions[0].params[0].name, "name")
        self.assertEqual(program.functions[0].params[0].type_ref, "string")
        self.assertEqual(program.functions[0].return_type, "string")
        self.assertEqual(run_subset_program(source, entry="greet", args=["hello"]), "hello")

    def test_typed_return_mismatch_fails_in_subset_typecheck(self):
        source = """
        fn greet(name: string) -> string {
            return true;
        }
        """
        with self.assertRaises(DiagnosticError) as ctx:
            typecheck_subset_program_v0(parse_subset_program(source), entry="greet", args=["hello"])
        self.assertEqual(ctx.exception.diagnostic.phase, "subset-typecheck")

    def test_typed_call_argument_mismatch_fails_in_subset_typecheck(self):
        source = """
        fn greet(name: string) -> string {
            return name;
        }

        fn main() -> string {
            return greet(true);
        }
        """
        with self.assertRaises(DiagnosticError) as ctx:
            typecheck_subset_program_v0(parse_subset_program(source), entry="main", args=[])
        self.assertEqual(ctx.exception.diagnostic.phase, "subset-typecheck")

    def test_typed_if_statement_condition_and_returns_pass(self):
        source = """
        fn main(flag: bool) -> string {
            if flag {
                return "a";
            } else {
                return "b";
            }
        }
        """
        result = typecheck_subset_program_v0(parse_subset_program(source), entry="main", args=[True])
        self.assertEqual(result.entry, "main")
        self.assertEqual(run_subset_program(source, entry="main", args=[True]), "a")

    def test_unit_return_rejects_string_return(self):
        source = """
        fn main() -> unit {
            return "x";
        }
        """
        with self.assertRaises(DiagnosticError) as ctx:
            typecheck_subset_program_v0(parse_subset_program(source), entry="main", args=[])
        self.assertEqual(ctx.exception.diagnostic.phase, "subset-typecheck")
