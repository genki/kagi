from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal


class KagiRuntimeError(RuntimeError):
    pass


LoanKind = Literal["idle", "mut", "shared"]


@dataclass(frozen=True)
class LoanState:
    kind: LoanKind
    key: int | None = None
    epoch: int | None = None
    readers_minus_one: int | None = None

    @staticmethod
    def idle() -> "LoanState":
        return LoanState("idle")

    @staticmethod
    def mut(key: int) -> "LoanState":
        return LoanState("mut", key=key)

    @staticmethod
    def shared(epoch: int, readers_minus_one: int) -> "LoanState":
        return LoanState("shared", epoch=epoch, readers_minus_one=readers_minus_one)

    def export(self) -> str:
        if self.kind == "idle":
            return "idle"
        if self.kind == "mut":
            return "mut"
        return f"shared {self.epoch}"


@dataclass(frozen=True)
class Cell:
    alive: bool
    loan: LoanState


Heap = dict[int, Cell]


@dataclass(frozen=True)
class Action:
    kind: Literal["borrow_mut", "end_mut", "borrow_shared", "end_shared", "drop"]
    owner: int
    value: int | None = None


@dataclass(frozen=True)
class ExecutionResult:
    heap: Heap
    trace: list[Heap]
    actions: list[Action]


def well_formed(heap: Heap) -> bool:
    for cell in heap.values():
        if cell.loan.kind != "idle" and not cell.alive:
            return False
    return True


def export_owner(heap: Heap, owner: int) -> str:
    return get_cell(heap, owner).loan.export()


def get_cell(heap: Heap, owner: int) -> Cell:
    if owner not in heap:
        raise KagiRuntimeError(f"unknown owner: {owner}")
    return heap[owner]


def set_cell(heap: Heap, owner: int, cell: Cell) -> Heap:
    updated = dict(heap)
    updated[owner] = cell
    return updated


def apply_action(heap: Heap, action: Action) -> Heap:
    cell = get_cell(heap, action.owner)

    if action.kind == "borrow_mut":
        key = require_value(action)
        if not cell.alive:
            raise KagiRuntimeError("borrow_mut requires alive owner")
        if cell.loan.kind != "idle":
            raise KagiRuntimeError("borrow_mut requires idle loan state")
        return set_cell(heap, action.owner, Cell(alive=True, loan=LoanState.mut(key)))

    if action.kind == "end_mut":
        key = require_value(action)
        if cell.loan != LoanState.mut(key):
            raise KagiRuntimeError("end_mut requires matching mut key")
        return set_cell(heap, action.owner, replace(cell, loan=LoanState.idle()))

    if action.kind == "borrow_shared":
        epoch = require_value(action)
        if not cell.alive:
            raise KagiRuntimeError("borrow_shared requires alive owner")
        if cell.loan.kind == "idle":
            return set_cell(heap, action.owner, Cell(alive=True, loan=LoanState.shared(epoch, 0)))
        if cell.loan.kind == "shared" and cell.loan.epoch == epoch:
            readers = (cell.loan.readers_minus_one or 0) + 1
            return set_cell(heap, action.owner, Cell(alive=True, loan=LoanState.shared(epoch, readers)))
        raise KagiRuntimeError("borrow_shared requires idle or same-epoch shared state")

    if action.kind == "end_shared":
        epoch = require_value(action)
        if cell.loan.kind != "shared" or cell.loan.epoch != epoch:
            raise KagiRuntimeError("end_shared requires matching shared epoch")
        readers = cell.loan.readers_minus_one or 0
        if readers == 0:
            return set_cell(heap, action.owner, replace(cell, loan=LoanState.idle()))
        return set_cell(heap, action.owner, replace(cell, loan=LoanState.shared(epoch, readers - 1)))

    if action.kind == "drop":
        if not cell.alive:
            raise KagiRuntimeError("drop requires alive owner")
        if cell.loan.kind != "idle":
            raise KagiRuntimeError("drop requires idle loan state")
        return set_cell(heap, action.owner, Cell(alive=False, loan=LoanState.idle()))

    raise KagiRuntimeError(f"unsupported action: {action.kind}")


def require_value(action: Action) -> int:
    if action.value is None:
        raise KagiRuntimeError(f"{action.kind} requires an integer parameter")
    return action.value


def parse_program(source: str) -> tuple[Heap, list[Action]]:
    heap: Heap = {}
    actions: list[Action] = []

    for lineno, raw_line in enumerate(source.splitlines(), start=1):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        head = parts[0]

        try:
            if head == "owner":
                owner = int(parts[1])
                alive = parse_alive(parts[2])
                loan = parse_loan(parts[3:])
                heap[owner] = Cell(alive=alive, loan=loan)
                continue

            if head == "borrow_mut":
                actions.append(Action("borrow_mut", int(parts[1]), int(parts[2])))
                continue
            if head == "end_mut":
                actions.append(Action("end_mut", int(parts[1]), int(parts[2])))
                continue
            if head == "borrow_shared":
                actions.append(Action("borrow_shared", int(parts[1]), int(parts[2])))
                continue
            if head == "end_shared":
                actions.append(Action("end_shared", int(parts[1]), int(parts[2])))
                continue
            if head == "drop":
                actions.append(Action("drop", int(parts[1])))
                continue
        except (IndexError, ValueError) as exc:
            raise KagiRuntimeError(f"parse error on line {lineno}: {raw_line}") from exc

        raise KagiRuntimeError(f"unknown statement on line {lineno}: {raw_line}")

    if not well_formed(heap):
        raise KagiRuntimeError("initial heap is not well-formed")

    return heap, actions


def parse_alive(token: str) -> bool:
    if token == "alive":
        return True
    if token == "dead":
        return False
    raise KagiRuntimeError(f"invalid alive state: {token}")


def parse_loan(tokens: list[str]) -> LoanState:
    if not tokens:
        raise KagiRuntimeError("missing loan state")
    if tokens[0] == "idle":
        return LoanState.idle()
    if tokens[0] == "mut":
        return LoanState.mut(int(tokens[1]))
    if tokens[0] == "shared":
        return LoanState.shared(int(tokens[1]), int(tokens[2]))
    raise KagiRuntimeError(f"invalid loan state: {' '.join(tokens)}")


def execute_program(source: str) -> ExecutionResult:
    heap, actions = parse_program(source)
    trace = [heap]
    current = heap
    for action in actions:
        current = apply_action(current, action)
        if not well_formed(current):
            raise KagiRuntimeError("heap became ill-formed")
        trace.append(current)
    return ExecutionResult(heap=current, trace=trace, actions=actions)


def action_to_string(action: Action) -> str:
    if action.value is None:
        return f"{action.kind} {action.owner}"
    return f"{action.kind} {action.owner} {action.value}"
