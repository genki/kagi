import json
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import Mock, patch

from kagi.artifact import PrintArtifactV1
from kagi.compile_result import compile_source_v1
from kagi.hir import lower_surface_program_to_hir_v1
from kagi.kir import KIRPrintV0, KIRProgramV0, KIRStringV0, serialize_kir_program_v0
from kagi.selfhost_bundle import parse_selfhost_pipeline_bundle_v1, selfhost_pipeline_bundle_v1_to_json
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
            raw_check="ok",
            raw_artifact='{"kind":"print_many","texts":["hello"]}',
            raw_compile='{"kind":"print_many","texts":["hello"]}',
            surface_ast=surface_ast,
            hir=hir,
            kir=kir,
            artifact=PrintArtifactV1(texts=["hello"]),
            compile_artifact=PrintArtifactV1(texts=["hello"]),
        )

        with patch("kagi.compile_result.execute_selfhost_frontend_entry_v1", return_value="bundle"):
            with patch("kagi.compile_result.parse_selfhost_pipeline_bundle_v1", return_value=bundle):
                compiled = compile_source_v1(frontend_source, "ignored source")

        self.assertEqual(compiled.lower.kir, kir)
        self.assertEqual(compiled.compile_kir, kir)

    def test_compile_source_v1_canonical_frontend_no_longer_calls_python_hir_to_kir_builtin(self):
        root = Path(__file__).resolve().parents[1]
        frontend_source = (root / "examples" / "selfhost_frontend.ks").read_text(encoding="utf-8")
        source = (root / "examples" / "hello.ksrc").read_text(encoding="utf-8")

        from kagi.bootstrap_builders import builtin_hir_to_kir
        import kagi.lower_subset_to_kir as lower_subset_to_kir

        spy = Mock(side_effect=builtin_hir_to_kir)
        with patch(
            "kagi.lower_subset_to_kir.SUBSET_KIR_BUILTINS",
            {**lower_subset_to_kir.SUBSET_KIR_BUILTINS, "hir_to_kir": spy},
        ):
            compiled = compile_source_v1(frontend_source, source)

        self.assertEqual(spy.call_count, 0)
        self.assertEqual(compiled.stdout, "hello, world!")

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
