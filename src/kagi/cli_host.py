from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Callable

from .diagnostics import DiagnosticError, diagnostic_from_runtime_error
from .ir import action_to_string


EmitPayload = Callable[[dict], None]
EmitText = Callable[[str], None]
EmitDiagnostic = Callable[[Exception], None]


def _runtime_api():
    from .runtime import KagiRuntimeError, execute_program_ir, export_owner, well_formed

    return KagiRuntimeError, execute_program_ir, export_owner, well_formed


def _frontend_api():
    from .frontend import execute_bootstrap_program, parse_bootstrap_program, parse_core_program

    return execute_bootstrap_program, parse_bootstrap_program, parse_core_program


def _selfhost_api():
    from .selfhost_runtime import (
        build_selfhost_frontend_v1,
        compile_selfhost_frontend_to_kir_v1,
        execute_selfhost_frontend_entry_v1,
        execute_selfhost_frontend_pipeline_bundle_v1,
    )

    return (
        build_selfhost_frontend_v1,
        compile_selfhost_frontend_to_kir_v1,
        execute_selfhost_frontend_entry_v1,
        execute_selfhost_frontend_pipeline_bundle_v1,
    )


def _subset_api():
    from .subset_eval import run_subset_program

    return run_subset_program


def heap_to_json(result: object) -> dict:
    _, _, export_owner, _ = _runtime_api()
    owners = {}
    for owner, cell in sorted(result.heap.items()):
        loan = {"kind": cell.loan.kind}
        if cell.loan.key is not None:
            loan["key"] = cell.loan.key
        if cell.loan.epoch is not None:
            loan["epoch"] = cell.loan.epoch
        if cell.loan.readers_minus_one is not None:
            loan["readers_minus_one"] = cell.loan.readers_minus_one

        owners[str(owner)] = {
            "alive": cell.alive,
            "loan": loan,
            "export": export_owner(result.heap, owner),
        }
    return {"owners": owners}


def trace_to_json(result: object) -> dict:
    steps = []
    for index, heap in enumerate(result.trace):
        steps.append(
            {
                "index": index,
                "action": None if index == 0 else action_to_string(result.actions[index - 1]),
                "owners": heap_to_json(type("TraceResult", (), {"heap": heap})())["owners"],
            }
        )
    return {"steps": steps}


def read_text_file(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def read_selfhost_sources(frontend_path: str, source_path: str) -> tuple[str, str]:
    return read_text_file(frontend_path), read_text_file(source_path)


def parse_selfhost_ast(frontend_source: str, program_source: str) -> object:
    _, _, execute_selfhost_frontend_entry_v1, _ = _selfhost_api()
    return execute_selfhost_frontend_entry_v1(frontend_source, entry="parse", args=[program_source])


def selfhost_metadata_v1() -> dict[str, str]:
    return {
        "contract_version": "front-half-v1",
        "frontend_entry": "pipeline",
    }


def parse_json_text(raw: str, *, phase: str, expected_kind: str | None = None) -> object:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DiagnosticError(
            diagnostic_from_runtime_error(phase, f"invalid json: {exc.msg}")
        ) from exc
    if expected_kind is not None:
        if not isinstance(payload, dict) or payload.get("kind") != expected_kind:
            raise DiagnosticError(
                diagnostic_from_runtime_error(phase, f"unsupported {expected_kind} payload")
            )
    return payload


def execute_selfhost_text_entry(frontend_source: str, program_source: str, *, entry: str) -> str:
    _, _, execute_selfhost_frontend_entry_v1, _ = _selfhost_api()
    value = execute_selfhost_frontend_entry_v1(frontend_source, entry=entry, args=[program_source])
    if not isinstance(value, str):
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-pipeline", f"{entry} entry must return a string")
        )
    if value.startswith("error:"):
        raise DiagnosticError(diagnostic_from_runtime_error("selfhost-pipeline", value))
    return value


def load_selfhost_pipeline_bundle(frontend_source: str, program_source: str):
    _, _, _, execute_selfhost_frontend_pipeline_bundle_v1 = _selfhost_api()
    return execute_selfhost_frontend_pipeline_bundle_v1(frontend_source, program_source)


def bundle_field_raw(bundle, field: str) -> str:
    mapping = {
        "ast": bundle.raw_ast,
        "hir": bundle.raw_hir,
        "kir": bundle.raw_kir,
        "analysis": bundle.raw_analysis,
        "check": bundle.raw_check,
        "artifact": bundle.raw_artifact,
        "compile": bundle.raw_compile,
    }
    if field not in mapping:
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-pipeline", f"missing bundle field: {field}")
        )
    return mapping[field]


def bundle_field_object(bundle, field: str) -> dict[str, object]:
    return parse_json_text(bundle_field_raw(bundle, field), phase="selfhost-pipeline")


def artifact_texts_from_raw(raw_artifact: str) -> list[str]:
    payload = parse_json_text(raw_artifact, phase="selfhost-artifact", expected_kind="print_many")
    assert isinstance(payload, dict)
    texts = payload.get("texts")
    if not isinstance(texts, list) or not all(isinstance(item, str) for item in texts):
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-artifact", "print_many requires texts")
        )
    return list(texts)


def stdout_from_raw_artifact(raw_artifact: str) -> str:
    return "\n".join(artifact_texts_from_raw(raw_artifact))


def capir_from_raw_artifact(raw_artifact: str) -> dict[str, object]:
    texts = artifact_texts_from_raw(raw_artifact)
    return {
        "effect": "print",
        "ops": [{"text": text} for text in texts],
        "serialized": "".join(f"print {json.dumps(text, ensure_ascii=False)}\n" for text in texts),
    }


def kir_from_pipeline_payload(bundle, *, raw_compile: str) -> dict[str, object]:
    kir = bundle_field_object(bundle, "kir")
    functions = kir.get("functions")
    instructions = kir.get("instructions")
    if isinstance(functions, list) and functions == [] and isinstance(instructions, list):
        texts: list[str] = []
        for item in instructions:
            if not isinstance(item, dict) or item.get("op") != "print":
                return kir
            expr = item.get("expr")
            if not isinstance(expr, dict) or expr.get("kind") != "string":
                return kir
            text = expr.get("value")
            if not isinstance(text, str):
                return kir
            texts.append(text)
        return {
            "kind": "kir",
            "effect": "print",
            "ops": [{"text": text} for text in texts],
            "stdout": stdout_from_raw_artifact(raw_compile),
        }
    return kir


def effects_from_pipeline_payload(bundle) -> dict[str, object]:
    analysis = bundle_field_object(bundle, "analysis")
    effects = analysis.get("effects")
    if not isinstance(effects, dict):
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-pipeline", "analysis requires effects")
        )
    return effects


def emit_diagnostic_default(exc: Exception, *, phase: str, use_json: bool, emit_payload: EmitPayload) -> None:
    KagiRuntimeError, _, _, _ = _runtime_api()
    if isinstance(exc, DiagnosticError):
        diagnostic = exc.diagnostic
    elif isinstance(exc, KagiRuntimeError):
        diagnostic = diagnostic_from_runtime_error(phase, str(exc))
    else:
        diagnostic = diagnostic_from_runtime_error(phase, str(exc))

    if use_json:
        emit_payload({"ok": False, "diagnostic": diagnostic.to_json()})
        raise SystemExit(1)

    location = ""
    if diagnostic.line is not None:
        location = f"{diagnostic.line}:{diagnostic.column or 1}: "
    print(
        f"{diagnostic.phase}:{diagnostic.code}: {location}{diagnostic.message}",
        file=sys.stderr,
    )
    if diagnostic.snippet:
        print(diagnostic.snippet, file=sys.stderr)
    raise SystemExit(1)


def run_cli_command(args, *, emit_payload: EmitPayload, emit_text: EmitText) -> None:
    def emit_diag(exc: Exception, *, phase: str, use_json: bool) -> None:
        emit_diagnostic_default(exc, phase=phase, use_json=use_json, emit_payload=emit_payload)

    if args.command == "run":
        try:
            _, _, parse_core_program = _frontend_api()
            _, execute_program_ir, _, _ = _runtime_api()
            source = read_text_file(args.file)
            result = execute_program_ir(parse_core_program(source))
            emit_payload(heap_to_json(result))
        except Exception as exc:
            emit_diag(exc, phase="runtime", use_json=args.json)
        return

    if args.command == "trace":
        try:
            _, _, parse_core_program = _frontend_api()
            _, execute_program_ir, _, _ = _runtime_api()
            source = read_text_file(args.file)
            result = execute_program_ir(parse_core_program(source))
            emit_payload(trace_to_json(result))
        except Exception as exc:
            emit_diag(exc, phase="runtime", use_json=args.json)
        return

    if args.command == "check":
        try:
            _, _, parse_core_program = _frontend_api()
            _, execute_program_ir, _, well_formed = _runtime_api()
            source = read_text_file(args.file)
            program = parse_core_program(source)
            result = execute_program_ir(program)
            emit_payload(
                {
                    "ok": True,
                    "initial_well_formed": well_formed(program.heap),
                    "action_count": len(program.actions),
                    "final_well_formed": well_formed(result.heap),
                }
            )
        except Exception as exc:
            emit_diag(exc, phase="runtime", use_json=args.json)
        return

    if args.command == "exports":
        try:
            _, _, parse_core_program = _frontend_api()
            _, execute_program_ir, export_owner, _ = _runtime_api()
            source = read_text_file(args.file)
            result = execute_program_ir(parse_core_program(source))
            emit_payload({str(owner): export_owner(result.heap, owner) for owner in sorted(result.heap.keys())})
        except Exception as exc:
            emit_diag(exc, phase="runtime", use_json=args.json)
        return

    if args.command == "bootstrap-check":
        try:
            execute_bootstrap_program, parse_bootstrap_program, _ = _frontend_api()
            _, _, _, well_formed = _runtime_api()
            source = read_text_file(args.file)
            program = parse_bootstrap_program(source)
            result = execute_bootstrap_program(source)
            emit_payload(
                {
                    "ok": True,
                    "owners": sorted(program.owner_ids.keys()),
                    "action_count": len(program.program.actions),
                    "assertion_count": len(program.assertions),
                    "final_well_formed": well_formed(result.heap),
                }
            )
        except Exception as exc:
            emit_diag(exc, phase="runtime", use_json=args.json)
        return

    if args.command == "bootstrap-trace":
        try:
            execute_bootstrap_program, _, _ = _frontend_api()
            source = read_text_file(args.file)
            result = execute_bootstrap_program(source)
            emit_payload(trace_to_json(result))
        except Exception as exc:
            emit_diag(exc, phase="runtime", use_json=args.json)
        return

    if args.command == "subset-run":
        try:
            run_subset_program = _subset_api()
            source = read_text_file(args.file)
            value = run_subset_program(source, entry=args.entry, args=list(args.arg))
            emit_payload({"ok": True, "entry": args.entry, "value": value})
        except Exception as exc:
            emit_diag(exc, phase="subset-runtime", use_json=args.json)
        return

    if args.command == "selfhost-run":
        try:
            frontend_source, program_source = read_selfhost_sources(args.frontend, args.source)
            if args.json:
                bundle = load_selfhost_pipeline_bundle(frontend_source, program_source)
                raw_ast = bundle_field_raw(bundle, "ast")
                raw_compile = bundle_field_raw(bundle, "compile")
                emit_payload(
                    {
                        "ok": True,
                        "entry": "pipeline",
                        "metadata": selfhost_metadata_v1(),
                        "source": str(args.source),
                        "ast": raw_ast,
                        "hir": bundle_field_object(bundle, "hir"),
                        "kir": kir_from_pipeline_payload(bundle, raw_compile=raw_compile),
                        "capir": capir_from_raw_artifact(raw_compile),
                        "artifact": raw_compile,
                        "value": stdout_from_raw_artifact(raw_compile),
                    }
                )
            else:
                raw_compile = execute_selfhost_text_entry(frontend_source, program_source, entry="compile")
                emit_text(stdout_from_raw_artifact(raw_compile))
        except Exception as exc:
            emit_diag(exc, phase="subset-runtime", use_json=args.json)
        return

    if args.command == "selfhost-check":
        try:
            frontend_source, program_source = read_selfhost_sources(args.frontend, args.source)
            bundle = load_selfhost_pipeline_bundle(frontend_source, program_source)
            emit_payload(
                {
                    "ok": True,
                    "entry": "pipeline",
                    "metadata": selfhost_metadata_v1(),
                    "source": str(args.source),
                    "ast": bundle_field_raw(bundle, "ast") if args.json else None,
                    "hir": bundle_field_object(bundle, "hir") if args.json else None,
                    "value": "ok",
                    "effects": effects_from_pipeline_payload(bundle),
                }
            )
        except DiagnosticError as exc:
            if exc.diagnostic.message == "error: unsupported source":
                emit_payload(
                    {
                        "ok": False,
                        "entry": "pipeline",
                        "source": str(args.source),
                        "ast": None,
                        "value": exc.diagnostic.message,
                    }
                )
                raise SystemExit(1)
            emit_diag(exc, phase="subset-runtime", use_json=args.json)
        except Exception as exc:
            emit_diag(exc, phase="subset-runtime", use_json=args.json)
        return

    if args.command == "selfhost-parse":
        try:
            frontend_source, program_source = read_selfhost_sources(args.frontend, args.source)
            value = parse_selfhost_ast(frontend_source, program_source)
            ok = not str(value).startswith("error:")
            emit_payload({"ok": ok, "entry": args.entry, "source": str(args.source), "ast": value})
            if not ok:
                raise SystemExit(1)
        except SystemExit:
            raise
        except Exception as exc:
            emit_diag(exc, phase="subset-runtime", use_json=args.json)
        return

    if args.command == "selfhost-emit":
        try:
            frontend_source, program_source = read_selfhost_sources(args.frontend, args.source)
            bundle = load_selfhost_pipeline_bundle(frontend_source, program_source)
            emit_payload(
                {
                    "ok": True,
                    "entry": "pipeline",
                    "metadata": selfhost_metadata_v1(),
                    "source": str(args.source),
                    "ast": bundle_field_raw(bundle, "ast"),
                    "hir": bundle_field_object(bundle, "hir"),
                    "artifact": bundle_field_raw(bundle, "artifact"),
                }
            )
        except SystemExit:
            raise
        except Exception as exc:
            emit_diag(exc, phase="subset-runtime", use_json=args.json)
        return

    if args.command == "selfhost-capir":
        try:
            frontend_source, program_source = read_selfhost_sources(args.frontend, args.source)
            bundle = load_selfhost_pipeline_bundle(frontend_source, program_source)
            raw_compile = bundle_field_raw(bundle, "compile")
            emit_payload(
                {
                    "ok": True,
                    "entry": "pipeline",
                    "metadata": selfhost_metadata_v1(),
                    "source": str(args.source),
                    "ast": bundle_field_raw(bundle, "ast"),
                    "hir": bundle_field_object(bundle, "hir"),
                    "artifact": raw_compile,
                    "kir": kir_from_pipeline_payload(bundle, raw_compile=raw_compile),
                    "capir": capir_from_raw_artifact(raw_compile),
                }
            )
        except SystemExit:
            raise
        except Exception as exc:
            emit_diag(exc, phase="subset-runtime", use_json=args.json)
        return

    if args.command == "selfhost-freeze":
        try:
            _, compile_selfhost_frontend_to_kir_v1, _, _ = _selfhost_api()
            frontend_source = read_text_file(args.frontend)
            kir_json = compile_selfhost_frontend_to_kir_v1(frontend_source)
            if args.json:
                emit_payload({"ok": True, "kir": json.loads(kir_json)})
            else:
                emit_text(kir_json)
        except Exception as exc:
            emit_diag(exc, phase="subset-runtime", use_json=args.json)
        return

    if args.command == "selfhost-build":
        try:
            build_selfhost_frontend_v1, _, _, _ = _selfhost_api()
            frontend_source = read_text_file(args.frontend)
            build = build_selfhost_frontend_v1(frontend_source)
            if args.json:
                emit_payload(
                    {
                        "ok": True,
                        "fixed_point": build.fixed_point,
                        "stage0_kir": json.loads(build.stage0_kir),
                        "stage1_kir": json.loads(build.stage1_kir),
                        "stage2_kir": json.loads(build.stage2_kir),
                    }
                )
            else:
                emit_text(build.stage1_kir)
        except Exception as exc:
            emit_diag(exc, phase="subset-runtime", use_json=args.json)
        return

    raise DiagnosticError(diagnostic_from_runtime_error("cli", f"unsupported command: {args.command}"))
