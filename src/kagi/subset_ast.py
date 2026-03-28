from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StringLiteral:
    value: str


@dataclass(frozen=True)
class BoolLiteral:
    value: bool


@dataclass(frozen=True)
class IntLiteral:
    value: int


@dataclass(frozen=True)
class Variable:
    name: str


@dataclass(frozen=True)
class Call:
    callee: str
    args: list["Expr"]


Expr = StringLiteral | BoolLiteral | IntLiteral | Variable | Call


@dataclass(frozen=True)
class LetStmt:
    name: str
    expr: Expr


@dataclass(frozen=True)
class ReturnStmt:
    expr: Expr


@dataclass(frozen=True)
class IfStmt:
    condition: Expr
    then_body: list["Stmt"]
    else_body: list["Stmt"]


@dataclass(frozen=True)
class ExprStmt:
    expr: Expr


Stmt = LetStmt | ReturnStmt | IfStmt | ExprStmt


@dataclass(frozen=True)
class FunctionDef:
    name: str
    params: list[str]
    body: list[Stmt]


@dataclass(frozen=True)
class SubsetProgram:
    functions: list[FunctionDef]


@dataclass(frozen=True)
class ReturnSignal:
    value: object
