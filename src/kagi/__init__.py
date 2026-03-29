from __future__ import annotations

from importlib import import_module

_EXPORTS = {
    "Action": (".ir", "Action"),
    "BootstrapProgram": (".frontend", "BootstrapProgram"),
    "CapIRArtifactResult": (".capir_runtime", "CapIRArtifactResult"),
    "CapIRExecutionResult": (".capir_runtime", "CapIRExecutionResult"),
    "CapIRFragment": (".ir", "CapIRFragment"),
    "CapIRPrint": (".ir", "CapIRPrint"),
    "Cell": (".runtime", "Cell"),
    "CheckArtifactV1": (".compile_result", "CheckArtifactV1"),
    "CompileResultV1": (".compile_result", "CompileResultV1"),
    "Diagnostic": (".diagnostics", "Diagnostic"),
    "DiagnosticError": (".diagnostics", "DiagnosticError"),
    "EffectSummaryV1": (".effects", "EffectSummaryV1"),
    "ExecutionResult": (".runtime", "ExecutionResult"),
    "FunctionDef": (".subset", "FunctionDef"),
    "ParamDef": (".subset", "ParamDef"),
    "Heap": (".runtime", "Heap"),
    "HIRFunctionV1": (".hir", "HIRFunctionV1"),
    "HIRProgramV1": (".hir", "HIRProgramV1"),
    "KagiHostCommandV1": (".host_abi", "KagiHostCommandV1"),
    "KagiHostResponseV1": (".host_abi", "KagiHostResponseV1"),
    "KIRExecutionResult": (".capir_runtime", "KIRExecutionResult"),
    "KIRExecutionContextV0": (".kir_runtime", "KIRExecutionContextV0"),
    "KIRPrintV0": (".kir", "KIRPrintV0"),
    "KIRProgramV0": (".kir", "KIRProgramV0"),
    "KagiRuntimeError": (".runtime", "KagiRuntimeError"),
    "LoanState": (".runtime", "LoanState"),
    "LowerArtifactV1": (".compile_result", "LowerArtifactV1"),
    "ParseArtifactV1": (".compile_result", "ParseArtifactV1"),
    "PrintArtifactV1": (".artifact", "PrintArtifactV1"),
    "ProgramIR": (".ir", "ProgramIR"),
    "ResolvedProgramV1": (".resolve", "ResolvedProgramV1"),
    "SelfhostPipelineBundleV1": (".selfhost_bundle", "SelfhostPipelineBundleV1"),
    "SelfhostBootstrapChainV1": (".selfhost_runtime", "SelfhostBootstrapChainV1"),
    "SubsetProgram": (".subset", "SubsetProgram"),
    "SubsetTypecheckResultV0": (".subset_typecheck", "SubsetTypecheckResultV0"),
    "SurfaceFunctionV1": (".surface_ast", "SurfaceFunctionV1"),
    "SurfaceProgramV1": (".surface_ast", "SurfaceProgramV1"),
    "TypecheckedProgramV1": (".typecheck", "TypecheckedProgramV1"),
    "action_to_string": (".ir", "action_to_string"),
    "apply_action": (".runtime", "apply_action"),
    "artifact_v1_stdout": (".artifact", "artifact_v1_stdout"),
    "artifact_v1_to_json": (".artifact", "artifact_v1_to_json"),
    "build_selfhost_frontend_v1": (".selfhost_runtime", "build_selfhost_frontend_v1"),
    "bootstrap_selfhost_frontend_v1": (".selfhost_runtime", "bootstrap_selfhost_frontend_v1"),
    "compile_selfhost_frontend_to_kir_v1": (".selfhost_runtime", "compile_selfhost_frontend_to_kir_v1"),
    "compile_source_v1": (".compile_result", "compile_source_v1"),
    "execute_and_inspect_capir_artifact": (".capir_runtime", "execute_and_inspect_capir_artifact"),
    "execute_bootstrap_program": (".frontend", "execute_bootstrap_program"),
    "execute_capir_artifact": (".capir_runtime", "execute_capir_artifact"),
    "execute_capir_fragment": (".capir_runtime", "execute_capir_fragment"),
    "execute_kir_program": (".capir_runtime", "execute_kir_program"),
    "execute_program_ir": (".runtime", "execute_program_ir"),
    "execute_selfhost_frontend_entry_v1": (".selfhost_runtime", "execute_selfhost_frontend_entry_v1"),
    "execute_selfhost_frontend_pipeline_bundle_v1": (".selfhost_runtime", "execute_selfhost_frontend_pipeline_bundle_v1"),
    "export_owner": (".runtime", "export_owner"),
    "infer_effects_v1": (".effects", "infer_effects_v1"),
    "inspect_capir_artifact": (".capir_runtime", "inspect_capir_artifact"),
    "inspect_kir_artifact": (".kir", "inspect_kir_artifact"),
    "inspect_kir_program": (".capir_runtime", "inspect_kir_program"),
    "kir_program_from_print_artifact": (".kir", "kir_program_from_print_artifact"),
    "host_command_from_argparse": (".host_abi", "host_command_from_argparse"),
    "parse_host_argv_v1": (".host_abi", "parse_host_argv_v1"),
    "parse_artifact_v1": (".artifact", "parse_artifact_v1"),
    "parse_bootstrap_program": (".frontend", "parse_bootstrap_program"),
    "parse_core_program": (".frontend", "parse_core_program"),
    "parse_selfhost_pipeline_bundle_v1": (".selfhost_bundle", "parse_selfhost_pipeline_bundle_v1"),
    "parse_subset_program": (".subset", "parse_subset_program"),
    "resolve_hir_program_v1": (".resolve", "resolve_hir_program_v1"),
    "run_subset_program": (".subset", "run_subset_program"),
    "execute_host_command_v1": (".cli_host", "execute_host_command_v1"),
    "run_host_command_v1": (".cli_host", "run_host_command_v1"),
    "run_subset_program_via_kir": (".subset", "run_subset_program_via_kir"),
    "selfhost_pipeline_bundle_v1_to_json": (".selfhost_bundle", "selfhost_pipeline_bundle_v1_to_json"),
    "serialize_capir_fragment": (".ir", "serialize_capir_fragment"),
    "serialize_kir_program_v0": (".kir", "serialize_kir_program_v0"),
    "serialize_program_ir": (".ir", "serialize_program_ir"),
    "typecheck_program_v1": (".typecheck", "typecheck_program_v1"),
    "typecheck_subset_program_v0": (".subset", "typecheck_subset_program_v0"),
    "well_formed": (".runtime", "well_formed"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _EXPORTS[name]
    value = getattr(import_module(module_name, __name__), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + __all__)
