from __future__ import annotations

import argparse
import json
from pathlib import Path

from .frontend import execute_bootstrap_program, parse_bootstrap_program
from .runtime import ExecutionResult, action_to_string, execute_program, export_owner, parse_program, well_formed


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


def main() -> None:
    parser = argparse.ArgumentParser(prog="kagi")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("file")

    trace_parser = subparsers.add_parser("trace")
    trace_parser.add_argument("file")

    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("file")

    exports_parser = subparsers.add_parser("exports")
    exports_parser.add_argument("file")

    bootstrap_parser = subparsers.add_parser("bootstrap-check")
    bootstrap_parser.add_argument("file")

    bootstrap_trace_parser = subparsers.add_parser("bootstrap-trace")
    bootstrap_trace_parser.add_argument("file")

    args = parser.parse_args()
    if args.command == "run":
        source = Path(args.file).read_text(encoding="utf-8")
        result = execute_program(source)
        print(json.dumps(heap_to_json(result), ensure_ascii=False, indent=2))
        return

    if args.command == "trace":
        source = Path(args.file).read_text(encoding="utf-8")
        result = execute_program(source)
        print(json.dumps(trace_to_json(result), ensure_ascii=False, indent=2))
        return

    if args.command == "check":
        source = Path(args.file).read_text(encoding="utf-8")
        heap, actions = parse_program(source)
        result = execute_program(source)
        payload = {
            "ok": True,
            "initial_well_formed": well_formed(heap),
            "action_count": len(actions),
            "final_well_formed": well_formed(result.heap),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    if args.command == "exports":
        source = Path(args.file).read_text(encoding="utf-8")
        result = execute_program(source)
        payload = {
            str(owner): export_owner(result.heap, owner)
            for owner in sorted(result.heap.keys())
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    if args.command == "bootstrap-check":
        source = Path(args.file).read_text(encoding="utf-8")
        program = parse_bootstrap_program(source)
        result = execute_bootstrap_program(source)
        payload = {
            "ok": True,
            "owners": sorted(program.owner_ids.keys()),
            "action_count": len(program.actions),
            "assertion_count": len(program.assertions),
            "final_well_formed": well_formed(result.heap),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    if args.command == "bootstrap-trace":
        source = Path(args.file).read_text(encoding="utf-8")
        result = execute_bootstrap_program(source)
        print(json.dumps(trace_to_json(result), ensure_ascii=False, indent=2))
        return


if __name__ == "__main__":
    main()
