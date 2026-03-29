import json
import subprocess
import sys
import unittest


class CPythonDependencyBoundaryTest(unittest.TestCase):
    def run_python(self, script: str) -> dict:
        completed = subprocess.run(
            [sys.executable, "-c", script],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(completed.stdout)

    def test_stage1_canonical_compile_path_freezes_current_host_boundary(self):
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
    "modules": {
        "kagi.cli": "kagi.cli" in sys.modules,
        "kagi.subset_parser": "kagi.subset_parser" in sys.modules,
        "kagi.subset_lexer": "kagi.subset_lexer" in sys.modules,
        "kagi.selfhost_runtime": "kagi.selfhost_runtime" in sys.modules,
        "kagi.selfhost_bundle": "kagi.selfhost_bundle" in sys.modules,
        "kagi.kir_runtime": "kagi.kir_runtime" in sys.modules,
    },
}))
"""
        )

        self.assertEqual(payload["stdout"], "hello, world!")
        self.assertFalse(payload["modules"]["kagi.cli"])
        self.assertFalse(payload["modules"]["kagi.subset_parser"])
        self.assertFalse(payload["modules"]["kagi.subset_lexer"])
        self.assertTrue(payload["modules"]["kagi.selfhost_runtime"])
        self.assertTrue(payload["modules"]["kagi.selfhost_bundle"])
        self.assertTrue(payload["modules"]["kagi.kir_runtime"])

    def test_stage1_canonical_compile_path_uses_snapshot_not_host_executor(self):
        payload = self.run_python(
            """
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "/home/vagrant/kagi/src")

from kagi.compile_result import compile_source_v1

examples = Path("/home/vagrant/kagi/examples")
frontend = (examples / "selfhost_frontend.ks").read_text(encoding="utf-8")
source = (examples / "hello_arg_fn.ksrc").read_text(encoding="utf-8")

with patch("kagi.selfhost_runtime.execute_kir_entry_v0", side_effect=AssertionError("host kir executor should stay off canonical compile path")):
    compiled = compile_source_v1(frontend, source)

print(json.dumps({"stdout": compiled.stdout}))
"""
        )

        self.assertEqual(payload["stdout"], "hello, world!")
