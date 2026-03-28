import json
import unittest

from kagi.diagnostics import DiagnosticError
from kagi.kir import (
    KIRCallExprV0,
    KIRCallV0,
    KIRFunctionV0,
    KIRLetV0,
    KIRPrintV0,
    KIRProgramV0,
    KIRReturnV0,
    KIRStringV0,
    KIRVarV0,
    parse_kir_program_v0,
    serialize_kir_program_v0,
)


class KirAbiTest(unittest.TestCase):
    def test_parse_kir_program_v0_roundtrips_print_only_payload(self):
        raw = '{"kind":"kir","effect":"print","ops":[{"text":"hello"},{"text":"world"}]}'
        program = parse_kir_program_v0(raw)
        self.assertEqual(program.instructions, [KIRPrintV0(expr=KIRStringV0(value="hello")), KIRPrintV0(expr=KIRStringV0(value="world"))])
        self.assertEqual(json.loads(serialize_kir_program_v0(program)), json.loads(raw))

    def test_parse_kir_program_v0_roundtrips_structured_payload(self):
        raw = json.dumps(
            {
                "kind": "kir",
                "functions": [
                    {
                        "name": "emit_suffix",
                        "params": ["name"],
                        "body": [
                            {
                                "op": "return",
                                "expr": {
                                    "kind": "call_expr",
                                    "callee": "concat",
                                    "args": [
                                        {"kind": "string", "value": "hello, "},
                                        {"kind": "var", "name": "name"},
                                    ],
                                },
                            }
                        ],
                    }
                ],
                "instructions": [
                    {
                        "op": "call",
                        "name": "emit_suffix",
                        "args": [{"kind": "string", "value": "world!"}],
                    },
                    {
                        "op": "print",
                        "expr": {"kind": "string", "value": "hello, world!"},
                    },
                ],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        program = parse_kir_program_v0(raw)
        self.assertEqual(program.functions[0].name, "emit_suffix")
        self.assertEqual(program.functions[0].params, ["name"])
        self.assertEqual(program.functions[0].body[0], KIRReturnV0(expr=KIRCallExprV0(callee="concat", args=[KIRStringV0(value="hello, "), KIRVarV0(name="name")])))
        self.assertEqual(program.instructions[0], KIRCallV0(name="emit_suffix", args=[KIRStringV0(value="world!")]))
        self.assertEqual(json.loads(serialize_kir_program_v0(program)), json.loads(raw))

    def test_parse_kir_program_v0_rejects_non_kir_payload(self):
        with self.assertRaises(DiagnosticError):
            parse_kir_program_v0('{"kind":"other"}')
