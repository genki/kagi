from __future__ import annotations

from dataclasses import dataclass
import json

from .artifact import PrintArtifactV1, artifact_v1_to_json, parse_artifact_v1
from .diagnostics import DiagnosticError, diagnostic_from_runtime_error
from .hir import HIRProgramV1, hir_program_v1_to_json, parse_hir_program_v1
from .surface_ast import SurfaceProgramV1, parse_surface_program_v1


@dataclass(frozen=True)
class SelfhostPipelineBundleV1:
    raw_ast: str
    raw_hir: str
    raw_check: str
    raw_artifact: str
    raw_compile: str
    surface_ast: SurfaceProgramV1
    hir: HIRProgramV1
    artifact: PrintArtifactV1
    compile_artifact: PrintArtifactV1


def _bundle_value_to_raw(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list, int, float, bool)) or value is None:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    raise DiagnosticError(
        diagnostic_from_runtime_error("selfhost-pipeline", "unsupported bundle payload")
    )


def parse_selfhost_pipeline_bundle_v1(bundle_raw: object) -> SelfhostPipelineBundleV1:
    if not isinstance(bundle_raw, str):
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-pipeline", "bundle must be a string")
        )
    try:
        bundle = json.loads(bundle_raw)
    except json.JSONDecodeError as exc:
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-pipeline", f"invalid bundle: {exc.msg}")
        ) from exc
    if not isinstance(bundle, dict) or bundle.get("kind") != "pipeline_bundle":
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-pipeline", "unsupported bundle payload")
        )

    raw_ast = _bundle_value_to_raw(bundle.get("ast"))
    raw_hir = _bundle_value_to_raw(bundle.get("hir"))
    raw_check = _bundle_value_to_raw(bundle.get("check"))
    raw_artifact = _bundle_value_to_raw(bundle.get("artifact"))
    raw_compile = _bundle_value_to_raw(bundle.get("compile"))

    if raw_check != "ok":
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-pipeline", "unsupported check payload")
        )

    artifact = parse_artifact_v1(raw_artifact)
    compile_artifact = parse_artifact_v1(raw_compile)
    if artifact != compile_artifact:
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-pipeline", "inconsistent bundle payload")
        )

    return SelfhostPipelineBundleV1(
        raw_ast=raw_ast,
        raw_hir=raw_hir,
        raw_check=raw_check,
        raw_artifact=raw_artifact,
        raw_compile=raw_compile,
        surface_ast=parse_surface_program_v1(raw_ast),
        hir=parse_hir_program_v1(raw_hir),
        artifact=artifact,
        compile_artifact=compile_artifact,
    )


def selfhost_pipeline_bundle_v1_to_json(bundle: SelfhostPipelineBundleV1) -> str:
    return json.dumps(
        {
            "kind": "pipeline_bundle",
            "ast": json.loads(bundle.raw_ast),
            "hir": json.loads(hir_program_v1_to_json(bundle.hir)),
            "check": bundle.raw_check,
            "artifact": json.loads(artifact_v1_to_json(bundle.artifact)),
            "compile": json.loads(artifact_v1_to_json(bundle.compile_artifact)),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
