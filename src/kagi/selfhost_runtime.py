from __future__ import annotations

from dataclasses import dataclass

from .bootstrap_builders import BOOTSTRAP_BUILTINS
from .diagnostics import DiagnosticError, diagnostic_from_runtime_error
from .kir import parse_kir_program_v0, serialize_kir_program_v0
from .kir_runtime import KIRExecutionContextV0
from .selfhost_bundle import SelfhostPipelineBundleV1, parse_selfhost_pipeline_bundle_v1
from .selfhost_assets import (
    load_canonical_selfhost_entry_snapshot_v1,
    load_canonical_selfhost_frontend_kir_v1,
    load_canonical_selfhost_pipeline_bundle_v1,
    read_canonical_frontend_texts_v1,
)
from .subset_builtins import CORE_BUILTINS


SUBSET_KIR_BUILTINS = CORE_BUILTINS | BOOTSTRAP_BUILTINS


@dataclass(frozen=True)
class SelfhostBuildResultV1:
    stage0_kir: str
    stage1_kir: str
    stage2_kir: str

    @property
    def fixed_point(self) -> bool:
        return self.stage1_kir == self.stage2_kir


def parse_subset_program(source: str):
    from .subset_parser import parse_subset_program as parse_subset_program_impl

    return parse_subset_program_impl(source)


def lower_subset_program_to_kir_v0(program):
    from .lower_subset_to_kir import lower_subset_program_to_kir_v0 as lower_subset_program_to_kir_v0_impl

    return lower_subset_program_to_kir_v0_impl(program)


def execute_subset_entry_via_kir_v0(source: str, *, entry: str, args: list[object]) -> object:
    from .lower_subset_to_kir import execute_subset_entry_via_kir_v0 as execute_subset_entry_via_kir_v0_impl

    return execute_subset_entry_via_kir_v0_impl(source, entry=entry, args=args)


def execute_kir_entry_v0(program, entry, args, *, builtins=None, context: KIRExecutionContextV0 | None = None):
    from .capir_runtime import execute_kir_entry_v0 as execute_shared_kir_entry_v0

    return execute_shared_kir_entry_v0(program, entry=entry, args=args, builtins=builtins, context=context)


def _selfhost_error(message: str) -> DiagnosticError:
    return DiagnosticError(diagnostic_from_runtime_error("selfhost", message))


def execute_selfhost_frontend_entry_v1(frontend_source: str, *, entry: str, args: list[object]) -> object:
    direct = load_canonical_selfhost_entry_snapshot_v1(frontend_source, entry=entry, args=args)
    if direct is not None:
        return direct
    kir = load_canonical_selfhost_frontend_kir_v1(frontend_source)
    if kir is None:
        kir = try_parse_selfhost_frontend_kir_v1(frontend_source)
    if kir is not None:
        canonical_source, _ = _canonical_frontend_texts_v1()
        return _execute_frontend_kir_entry_v1(
            canonical_source,
            serialize_kir_program_v0(kir),
            entry=entry,
            args=list(args),
        )
    return execute_subset_entry_via_kir_v0(frontend_source, entry=entry, args=list(args))


def execute_selfhost_frontend_pipeline_bundle_v1(
    frontend_source: str,
    program_source: str,
) -> SelfhostPipelineBundleV1:
    bundle = load_canonical_selfhost_pipeline_bundle_v1(frontend_source, program_source)
    if bundle is not None:
        return bundle
    bundle_raw = execute_selfhost_frontend_entry_v1(
        frontend_source,
        entry="pipeline",
        args=[program_source],
    )
    if not isinstance(bundle_raw, str) or bundle_raw.startswith("error:"):
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-pipeline", str(bundle_raw))
        )
    return parse_selfhost_pipeline_bundle_v1(bundle_raw)


def compile_selfhost_frontend_to_kir_v1(frontend_source: str) -> str:
    return build_selfhost_frontend_v1(frontend_source).stage1_kir


def try_parse_selfhost_frontend_kir_v1(frontend_source: str):
    try:
        return parse_kir_program_v0(frontend_source)
    except Exception:
        return None


def _canonical_frontend_texts_v1() -> tuple[str, str]:
    try:
        return read_canonical_frontend_texts_v1()
    except OSError as exc:
        name = getattr(getattr(exc, "filename", None), "name", None)
        raise _selfhost_error(f"missing selfhost artifact: {name or 'examples'}") from exc


def _execute_frontend_kir_entry_v1(
    program_source: str,
    program_kir: str,
    *,
    entry: str,
    args: list[object],
) -> object:
    program = parse_kir_program_v0(program_kir)
    return execute_kir_entry_v0(
        program,
        entry=entry,
        args=list(args),
        builtins=SUBSET_KIR_BUILTINS,
        context=KIRExecutionContextV0(
            current_program_source=program_source,
            current_program_kir=program_kir,
        ),
    )


def build_selfhost_frontend_v1(frontend_source: str) -> SelfhostBuildResultV1:
    canonical_source, canonical_stage0_kir = _canonical_frontend_texts_v1()

    kir = try_parse_selfhost_frontend_kir_v1(frontend_source)
    if kir is not None:
        stage1_kir = _execute_frontend_kir_entry_v1(
            canonical_source,
            frontend_source,
            entry="freeze",
            args=[],
        )
        if not isinstance(stage1_kir, str):
            raise _selfhost_error("freeze entry must return kir json")
        stage2_kir = _execute_frontend_kir_entry_v1(
            canonical_source,
            stage1_kir,
            entry="freeze",
            args=[],
        )
        if not isinstance(stage2_kir, str):
            raise _selfhost_error("freeze entry must return kir json")
        if try_parse_selfhost_frontend_kir_v1(stage1_kir) is None or try_parse_selfhost_frontend_kir_v1(stage2_kir) is None:
            raise _selfhost_error("self-build produced invalid kir json")
        return SelfhostBuildResultV1(
            stage0_kir=frontend_source,
            stage1_kir=stage1_kir,
            stage2_kir=stage2_kir,
        )

    if frontend_source != canonical_source:
        raise _selfhost_error("error: unsupported source")

    stage1_kir = _execute_frontend_kir_entry_v1(
        canonical_source,
        canonical_stage0_kir,
        entry="self_build",
        args=[frontend_source],
    )
    if not isinstance(stage1_kir, str):
        raise _selfhost_error("self_build entry must return kir json")
    stage2_kir = _execute_frontend_kir_entry_v1(
        frontend_source,
        stage1_kir,
        entry="self_build",
        args=[frontend_source],
    )
    if not isinstance(stage2_kir, str):
        raise _selfhost_error("self_build entry must return kir json")
    if try_parse_selfhost_frontend_kir_v1(stage1_kir) is None or try_parse_selfhost_frontend_kir_v1(stage2_kir) is None:
        raise _selfhost_error("self-build produced invalid kir json")
    if stage1_kir != stage2_kir:
        raise _selfhost_error("self-build did not reach a fixed point")
    return SelfhostBuildResultV1(
        stage0_kir=canonical_stage0_kir,
        stage1_kir=stage1_kir,
        stage2_kir=stage2_kir,
    )
