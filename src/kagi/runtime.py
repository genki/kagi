from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

from .ir import Action, ProgramIR


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


def execute_program_ir(program: ProgramIR) -> ExecutionResult:
    if not well_formed(program.heap):
        raise KagiRuntimeError("initial heap is not well-formed")

    trace = [program.heap]
    current = program.heap
    for action in program.actions:
        current = apply_action(current, action)
        if not well_formed(current):
            raise KagiRuntimeError("heap became ill-formed")
        trace.append(current)
    return ExecutionResult(heap=current, trace=trace, actions=program.actions)
