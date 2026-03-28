import json
import subprocess
import sys
import unittest


class SubsetParserHostDependencyTest(unittest.TestCase):
    def run_python(self, script: str) -> dict:
        completed = subprocess.run(
            [sys.executable, "-c", script],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(completed.stdout)

    def test_canonical_compile_path_does_not_import_subset_parser_modules(self):
        payload = self.run_python(
            """
import json
import sys
from pathlib import Path

sys.path.insert(0, "/home/vagrant/kagi/src")

from kagi.compile_result import compile_source_v1

examples = Path("/home/vagrant/kagi/examples")
frontend = (examples / "selfhost_frontend.ks").read_text(encoding="utf-8")
source = (examples / "hello_arg_fn.ksrc").read_text(encoding="utf-8")
compiled = compile_source_v1(frontend, source)

print(json.dumps({
    "stdout": compiled.stdout,
    "subset_parser_loaded": "kagi.subset_parser" in sys.modules,
    "subset_lexer_loaded": "kagi.subset_lexer" in sys.modules,
}))
"""
        )

        self.assertEqual(payload["stdout"], "hello, world!")
        self.assertFalse(payload["subset_parser_loaded"])
        self.assertFalse(payload["subset_lexer_loaded"])

    def test_subset_parse_api_still_loads_parser_on_demand(self):
        payload = self.run_python(
            """
import json
import sys

sys.path.insert(0, "/home/vagrant/kagi/src")

from kagi.subset import parse_subset_program

program = parse_subset_program('fn main() { return "hello"; }')

print(json.dumps({
    "functions": len(program.functions),
    "subset_parser_loaded": "kagi.subset_parser" in sys.modules,
    "subset_lexer_loaded": "kagi.subset_lexer" in sys.modules,
}))
"""
        )

        self.assertEqual(payload["functions"], 1)
        self.assertTrue(payload["subset_parser_loaded"])
        self.assertTrue(payload["subset_lexer_loaded"])

    def test_noncanonical_kir_execution_path_does_not_import_subset_parser_modules(self):
        payload = self.run_python(
            """
import json
import sys
from pathlib import Path

sys.path.insert(0, "/home/vagrant/kagi/src")

from kagi.selfhost_runtime import compile_selfhost_frontend_to_kir_v1, execute_selfhost_frontend_entry_v1

examples = Path("/home/vagrant/kagi/examples")
frontend = (examples / "selfhost_frontend.ks").read_text(encoding="utf-8")
source = (examples / "hello_arg_fn.ksrc").read_text(encoding="utf-8")
kir_json = compile_selfhost_frontend_to_kir_v1(frontend)
sys.modules.pop("kagi.subset_parser", None)
sys.modules.pop("kagi.subset_lexer", None)
value = execute_selfhost_frontend_entry_v1(kir_json, entry="pipeline", args=[source])

print(json.dumps({
    "is_string": isinstance(value, str),
    "subset_parser_loaded": "kagi.subset_parser" in sys.modules,
    "subset_lexer_loaded": "kagi.subset_lexer" in sys.modules,
}))
"""
        )

        self.assertTrue(payload["is_string"])
        self.assertFalse(payload["subset_parser_loaded"])
        self.assertFalse(payload["subset_lexer_loaded"])

    def test_noncanonical_kir_compile_path_does_not_import_subset_parser_modules(self):
        payload = self.run_python(
            """
import json
import sys
from pathlib import Path

sys.path.insert(0, "/home/vagrant/kagi/src")

from kagi.selfhost_runtime import compile_selfhost_frontend_to_kir_v1

examples = Path("/home/vagrant/kagi/examples")
frontend = (examples / "selfhost_frontend.ks").read_text(encoding="utf-8")
kir_json = compile_selfhost_frontend_to_kir_v1(frontend)
sys.modules.pop("kagi.subset_parser", None)
sys.modules.pop("kagi.subset_lexer", None)
compiled = compile_selfhost_frontend_to_kir_v1(kir_json)

print(json.dumps({
    "is_kir": compiled.startswith('{"kind":"kir"'),
    "subset_parser_loaded": "kagi.subset_parser" in sys.modules,
    "subset_lexer_loaded": "kagi.subset_lexer" in sys.modules,
}))
"""
        )

        self.assertTrue(payload["is_kir"])
        self.assertFalse(payload["subset_parser_loaded"])
        self.assertFalse(payload["subset_lexer_loaded"])
