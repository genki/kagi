from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .capir_runtime import capir_fragment_from_artifact, execute_capir_artifact
from .diagnostics import DiagnosticError, diagnostic_from_runtime_error
from .frontend import execute_bootstrap_program, parse_bootstrap_program, parse_core_program
from .ir import action_to_string, serialize_capir_fragment
from .runtime import ExecutionResult, KagiRuntimeError, execute_program_ir, export_owner, well_formed
from .selfhost import lower_tiny_program_to_capir, parse_tiny_program_ast_json
from .subset import run_subset_program


def heap_to_json(result: ExecutionResult) -> dict:
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


def trace_to_json(result: ExecutionResult) -> dict:
    steps = []
    for index, heap in enumerate(result.trace):
        steps.append(
            {
                "index": index,
                "action": None if index == 0 else action_to_string(result.actions[index - 1]),
                "owners": heap_to_json(ExecutionResult(heap=heap, trace=[], actions=[]))["owners"],
            }
        )
    return {"steps": steps}


def add_json_flag(command_parser: argparse.ArgumentParser) -> None:
    command_parser.add_argument("--json", action="store_true")


def emit_payload(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def emit_text(text: str) -> None:
    print(text, end="" if text.endswith("\n") else "\n")


def emit_diagnostic(exc: Exception, *, phase: str, use_json: bool) -> None:
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


def main() -> None:
    parser = argparse.ArgumentParser(prog="kagi")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("file")
    add_json_flag(run_parser)

    trace_parser = subparsers.add_parser("trace")
    trace_parser.add_argument("file")
    add_json_flag(trace_parser)

    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("file")
    add_json_flag(check_parser)

    exports_parser = subparsers.add_parser("exports")
    exports_parser.add_argument("file")
    add_json_flag(exports_parser)

    bootstrap_parser = subparsers.add_parser("bootstrap-check")
    bootstrap_parser.add_argument("file")
    add_json_flag(bootstrap_parser)

    bootstrap_trace_parser = subparsers.add_parser("bootstrap-trace")
    bootstrap_trace_parser.add_argument("file")
    add_json_flag(bootstrap_trace_parser)

    subset_run_parser = subparsers.add_parser("subset-run")
    subset_run_parser.add_argument("file")
    subset_run_parser.add_argument("--entry", default="main")
    subset_run_parser.add_argument("--arg", action="append", default=[])
    add_json_flag(subset_run_parser)

    selfhost_run_parser = subparsers.add_parser("selfhost-run")
    selfhost_run_parser.add_argument("frontend")
    selfhost_run_parser.add_argument("source")
    selfhost_run_parser.add_argument("--entry", default="compile")
    add_json_flag(selfhost_run_parser)

    selfhost_check_parser = subparsers.add_parser("selfhost-check")
    selfhost_check_parser.add_argument("frontend")
    selfhost_check_parser.add_argument("source")
    selfhost_check_parser.add_argument("--entry", default="check")
    add_json_flag(selfhost_check_parser)

    selfhost_parse_parser = subparsers.add_parser("selfhost-parse")
    selfhost_parse_parser.add_argument("frontend")
    selfhost_parse_parser.add_argument("source")
    selfhost_parse_parser.add_argument("--entry", default="parse")
    add_json_flag(selfhost_parse_parser)

    selfhost_emit_parser = subparsers.add_parser("selfhost-emit")
    selfhost_emit_parser.add_argument("frontend")
    selfhost_emit_parser.add_argument("source")
    selfhost_emit_parser.add_argument("--entry", default="lower")
    add_json_flag(selfhost_emit_parser)

    selfhost_capir_parser = subparsers.add_parser("selfhost-capir")
    selfhost_capir_parser.add_argument("frontend")
    selfhost_capir_parser.add_argument("source")
    selfhost_capir_parser.add_argument("--entry", default="parse")
    add_json_flag(selfhost_capir_parser)

    args = parser.parse_args()
    if args.command == "run":
        try:
            source = Path(args.file).read_text(encoding="utf-8")
            result = execute_program_ir(parse_core_program(source))
            emit_payload(heap_to_json(result))
        except Exception as exc:
            emit_diagnostic(exc, phase="runtime", use_json=args.json)
        return

    if args.command == "trace":
        try:
            source = Path(args.file).read_text(encoding="utf-8")
            result = execute_program_ir(parse_core_program(source))
            emit_payload(trace_to_json(result))
        except Exception as exc:
            emit_diagnostic(exc, phase="runtime", use_json=args.json)
        return

    if args.command == "check":
        try:
            source = Path(args.file).read_text(encoding="utf-8")
            program = parse_core_program(source)
            result = execute_program_ir(program)
            payload = {
                "ok": True,
                "initial_well_formed": well_formed(program.heap),
                "action_count": len(program.actions),
                "final_well_formed": well_formed(result.heap),
            }
            emit_payload(payload)
        except Exception as exc:
            emit_diagnostic(exc, phase="runtime", use_json=args.json)
        return

    if args.command == "exports":
        try:
            source = Path(args.file).read_text(encoding="utf-8")
            result = execute_program_ir(parse_core_program(source))
            payload = {
                str(owner): export_owner(result.heap, owner)
                for owner in sorted(result.heap.keys())
            }
            emit_payload(payload)
        except Exception as exc:
            emit_diagnostic(exc, phase="runtime", use_json=args.json)
        return

    if args.command == "bootstrap-check":
        try:
            source = Path(args.file).read_text(encoding="utf-8")
            program = parse_bootstrap_program(source)
            result = execute_bootstrap_program(source)
            payload = {
                "ok": True,
                "owners": sorted(program.owner_ids.keys()),
                "action_count": len(program.program.actions),
                "assertion_count": len(program.assertions),
                "final_well_formed": well_formed(result.heap),
            }
            emit_payload(payload)
        except Exception as exc:
            emit_diagnostic(exc, phase="runtime", use_json=args.json)
        return

    if args.command == "bootstrap-trace":
        try:
            source = Path(args.file).read_text(encoding="utf-8")
            result = execute_bootstrap_program(source)
            emit_payload(trace_to_json(result))
        except Exception as exc:
            emit_diagnostic(exc, phase="runtime", use_json=args.json)
        return

    if args.command == "subset-run":
        try:
            source = Path(args.file).read_text(encoding="utf-8")
            value = run_subset_program(source, entry=args.entry, args=list(args.arg))
            emit_payload({"ok": True, "entry": args.entry, "value": value})
        except Exception as exc:
            emit_diagnostic(exc, phase="subset-runtime", use_json=args.json)
        return

    if args.command == "selfhost-run":
        try:
            frontend_source = Path(args.frontend).read_text(encoding="utf-8")
            program_source = Path(args.source).read_text(encoding="utf-8")
            ast = run_subset_program(frontend_source, entry="parse", args=[program_source])
            artifact = run_subset_program(frontend_source, entry=args.entry, args=[program_source])
            capir = capir_fragment_from_artifact(artifact)
            value = execute_capir_artifact(artifact).output
            if args.json:
                emit_payload(
                    {
                        "ok": True,
                        "entry": args.entry,
                        "source": str(args.source),
                        "ast": ast,
                        "capir": {
                            "effect": capir.effect,
                            "ops": [{"text": op.text} for op in capir.ops],
                            "serialized": serialize_capir_fragment(capir),
                        },
                        "artifact": artifact,
                        "value": value,
                    }
                )
            else:
                emit_text(value)
        except Exception as exc:
            emit_diagnostic(exc, phase="subset-runtime", use_json=args.json)
        return

    if args.command == "selfhost-check":
        try:
            frontend_source = Path(args.frontend).read_text(encoding="utf-8")
            program_source = Path(args.source).read_text(encoding="utf-8")
            ast = run_subset_program(frontend_source, entry="parse", args=[program_source])
            if isinstance(ast, str) and ast.startswith("error:"):
                value = ast
                ok = False
            else:
                parse_tiny_program_ast_json(ast)
                value = run_subset_program(frontend_source, entry=args.entry, args=[program_source])
                ok = value == "ok"
            emit_payload(
                {
                    "ok": ok,
                    "entry": args.entry,
                    "source": str(args.source),
                    "ast": None if isinstance(ast, str) and ast.startswith("error:") else ast,
                    "value": value,
                }
            )
            if not ok:
                raise SystemExit(1)
        except SystemExit:
            raise
        except Exception as exc:
            emit_diagnostic(exc, phase="subset-runtime", use_json=args.json)
        return

    if args.command == "selfhost-parse":
        try:
            frontend_source = Path(args.frontend).read_text(encoding="utf-8")
            program_source = Path(args.source).read_text(encoding="utf-8")
            value = run_subset_program(frontend_source, entry=args.entry, args=[program_source])
            ok = not str(value).startswith("error:")
            emit_payload(
                {
                    "ok": ok,
                    "entry": args.entry,
                    "source": str(args.source),
                    "ast": value,
                }
            )
            if not ok:
                raise SystemExit(1)
        except SystemExit:
            raise
        except Exception as exc:
            emit_diagnostic(exc, phase="subset-runtime", use_json=args.json)
        return

    if args.command == "selfhost-emit":
        try:
            frontend_source = Path(args.frontend).read_text(encoding="utf-8")
            program_source = Path(args.source).read_text(encoding="utf-8")
            ast = run_subset_program(frontend_source, entry="parse", args=[program_source])
            if isinstance(ast, str) and ast.startswith("error:"):
                value = ast
                ok = False
            else:
                value = run_subset_program(frontend_source, entry=args.entry, args=[program_source])
                ok = execute_capir_artifact(value).output is not None
            emit_payload(
                {
                    "ok": ok,
                    "entry": args.entry,
                    "source": str(args.source),
                    "ast": None if isinstance(ast, str) and ast.startswith("error:") else ast,
                    "artifact": value,
                }
            )
            if not ok:
                raise SystemExit(1)
        except SystemExit:
            raise
        except Exception as exc:
            emit_diagnostic(exc, phase="subset-runtime", use_json=args.json)
        return

    if args.command == "selfhost-capir":
        try:
            frontend_source = Path(args.frontend).read_text(encoding="utf-8")
            program_source = Path(args.source).read_text(encoding="utf-8")
            ast = run_subset_program(frontend_source, entry=args.entry, args=[program_source])
            if isinstance(ast, str) and ast.startswith("error:"):
                emit_payload(
                    {
                        "ok": False,
                        "entry": args.entry,
                        "source": str(args.source),
                        "ast": None,
                        "capir": None,
                        "message": ast,
                    }
                )
                raise SystemExit(1)
            tiny_program = parse_tiny_program_ast_json(ast)
            capir = lower_tiny_program_to_capir(tiny_program)
            emit_payload(
                {
                    "ok": True,
                    "entry": args.entry,
                    "source": str(args.source),
                    "ast": ast,
                    "capir": {
                        "effect": capir.effect,
                        "ops": [{"text": op.text} for op in capir.ops],
                        "serialized": serialize_capir_fragment(capir),
                    },
                }
            )
        except SystemExit:
            raise
        except Exception as exc:
            emit_diagnostic(exc, phase="subset-runtime", use_json=args.json)
        return


if __name__ == "__main__":
    main()
