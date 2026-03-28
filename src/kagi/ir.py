from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ActionKind = Literal["borrow_mut", "end_mut", "borrow_shared", "end_shared", "drop"]


@dataclass(frozen=True)
class Action:
    kind: ActionKind
    owner: int
    value: int | None = None


@dataclass(frozen=True)
class ProgramIR:
    heap: dict
    actions: list[Action]


def action_to_string(action: Action) -> str:
    if action.value is None:
        return f"{action.kind} {action.owner}"
    return f"{action.kind} {action.owner} {action.value}"


def serialize_program_ir(program: ProgramIR) -> str:
    lines: list[str] = []
    for owner, cell in sorted(program.heap.items()):
        if cell.loan.kind == "idle":
            loan = "idle"
        elif cell.loan.kind == "mut":
            loan = f"mut {cell.loan.key}"
        else:
            loan = f"shared {cell.loan.epoch} {cell.loan.readers_minus_one}"
        alive = "alive" if cell.alive else "dead"
        lines.append(f"owner {owner} {alive} {loan}")

    if program.actions and lines:
        lines.append("")

    for action in program.actions:
        lines.append(action_to_string(action))

    return "\n".join(lines) + ("\n" if lines else "")
