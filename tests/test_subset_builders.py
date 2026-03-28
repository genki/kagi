import json
import unittest

from kagi.subset import run_subset_program


class SubsetBuilderTest(unittest.TestCase):
    def test_program_two_prints_ast_matches_current_shape(self):
        source = """
        fn main() {
            return program_two_prints_ast("hello", "world");
        }
        """
        value = run_subset_program(source, entry="main", args=[])
        self.assertEqual(
            json.loads(value),
            {
                "kind": "program",
                "functions": [],
                "statements": [
                    {"kind": "print", "expr": {"kind": "string", "value": "hello"}},
                    {"kind": "print", "expr": {"kind": "string", "value": "world"}},
                ],
            },
        )

    def test_program_zero_arg_fn_call_ast_matches_current_shape(self):
        source = """
        fn main() {
            return program_zero_arg_fn_call_ast("emit_greeting", "greeting", "hello, ", "world!");
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
        )

    def test_program_if_expr_print_ast_matches_current_shape(self):
        source = """
        fn main() {
            return program_if_expr_print_ast("greeting", "hello, ", "world!", "enabled", "hello, world!", "disabled");
        }
        """
        value = run_subset_program(source, entry="main", args=[])
        payload = json.loads(value)
        self.assertEqual(payload["kind"], "program")
        self.assertEqual(payload["statements"][2]["kind"], "print")
        self.assertEqual(payload["statements"][2]["expr"]["kind"], "if")

    def test_program_if_stmt_ast_matches_current_shape(self):
        source = """
        fn main() {
            return program_if_stmt_ast("greeting", "hello, ", "world!", "enabled", "hello, world!", "disabled");
        }
        """
        value = run_subset_program(source, entry="main", args=[])
        payload = json.loads(value)
        self.assertEqual(payload["kind"], "program")
        self.assertEqual(payload["statements"][2]["kind"], "if_stmt")
        self.assertEqual(payload["statements"][2]["then_body"][0]["kind"], "print")


if __name__ == "__main__":
    unittest.main()
