from __future__ import annotations

from dataclasses import dataclass

from .diagnostics import Diagnostic, DiagnosticError
from .subset_ast import BoolLiteral, Call, Expr, ExprStmt, FunctionDef, IfStmt, IntLiteral, LetStmt, ReturnStmt, Stmt, StringLiteral, SubsetProgram, Variable


TypeRef = str
KNOWN_TYPES = {"string", "int", "bool", "unit"}


@dataclass(frozen=True)
class BuiltinSignatureV0:
    arg_types: tuple[TypeRef | None, ...]
    return_type: TypeRef


@dataclass(frozen=True)
class SubsetTypecheckResultV0:
    program: SubsetProgram
    entry: str | None


BUILTIN_SIGNATURES: dict[str, BuiltinSignatureV0] = {
    "after_substring": BuiltinSignatureV0(("string", "string"), "string"),
    "before_substring": BuiltinSignatureV0(("string", "string"), "string"),
    "concat": BuiltinSignatureV0(("string", "string"), "string"),
    "ends_with": BuiltinSignatureV0(("string", "string"), "bool"),
    "extract_quoted": BuiltinSignatureV0(("string",), "string"),
    "hir_to_kir": BuiltinSignatureV0(("string",), "string"),
    "hir_to_analysis": BuiltinSignatureV0(("string",), "string"),
    "is_identifier": BuiltinSignatureV0(("string",), "bool"),
    "line_at": BuiltinSignatureV0(("string", "int"), "string"),
    "line_count": BuiltinSignatureV0(("string",), "int"),
    "print_ast": BuiltinSignatureV0(("string",), "string"),
    "print_many_artifact": BuiltinSignatureV0(("string",), "string"),
    "program_ast": BuiltinSignatureV0(("string",), "string"),
    "program_ast_to_hir": BuiltinSignatureV0(("string",), "string"),
    "program_if_expr_print_ast": BuiltinSignatureV0(("string", "string", "string", "string", "string", "string"), "string"),
    "program_if_stmt_ast": BuiltinSignatureV0(("string", "string", "string", "string", "string", "string"), "string"),
    "program_let_concat_print_ast": BuiltinSignatureV0(("string", "string", "string"), "string"),
    "program_let_print_ast": BuiltinSignatureV0(("string", "string"), "string"),
    "program_print_concat_ast": BuiltinSignatureV0(("string", "string"), "string"),
    "program_single_arg_fn_call_ast": BuiltinSignatureV0(("string", "string", "string", "string"), "string"),
    "program_text": BuiltinSignatureV0(("string",), "string"),
    "program_two_prints_ast": BuiltinSignatureV0(("string", "string"), "string"),
    "program_zero_arg_fn_call_ast": BuiltinSignatureV0(("string", "string", "string", "string"), "string"),
    "quote": BuiltinSignatureV0((), "string"),
    "starts_with": BuiltinSignatureV0(("string", "string"), "bool"),
    "trim": BuiltinSignatureV0(("string",), "string"),
}


def typecheck_subset_program_v0(
    program: SubsetProgram,
    *,
    entry: str | None = None,
    args: list[object] | None = None,
) -> SubsetTypecheckResultV0:
    functions = {fn.name: fn for fn in program.functions}
    if len(functions) != len(program.functions):
        raise _error("duplicate function definition")

    for fn in program.functions:
        _validate_function_signature(fn)

    if entry is not None:
        if entry not in functions:
            raise _error(f"unknown entry function: {entry}")
        if args is not None:
            _check_entry_args(functions[entry], list(args))

    for fn in program.functions:
        env = {param.name: param.type_ref for param in fn.params}
        _typecheck_block(fn.body, env, functions, fn.return_type)

    return SubsetTypecheckResultV0(program=program, entry=entry)


def _validate_function_signature(fn: FunctionDef) -> None:
    seen: set[str] = set()
    for param in fn.params:
        if param.name in seen:
            raise _error(f"duplicate parameter: {param.name}")
        seen.add(param.name)
        if param.type_ref is not None and param.type_ref not in KNOWN_TYPES:
            raise _error(f"unknown type: {param.type_ref}")
    if fn.return_type is not None and fn.return_type not in KNOWN_TYPES:
        raise _error(f"unknown type: {fn.return_type}")


def _check_entry_args(fn: FunctionDef, args: list[object]) -> None:
    if len(fn.params) != len(args):
        raise _error(f"{fn.name} expects {len(fn.params)} arguments, got {len(args)}")
    for param, value in zip(fn.params, args):
        if param.type_ref is None:
            continue
        actual = _runtime_type_of(value)
        if actual is None or actual != param.type_ref:
            raise _error(f"entry argument type mismatch for {param.name}: expected {param.type_ref}, got {actual or 'unknown'}")


def _typecheck_block(
    body: list[Stmt],
    env: dict[str, TypeRef | None],
    functions: dict[str, FunctionDef],
    return_type: TypeRef | None,
) -> None:
    local_env = dict(env)
    for stmt in body:
        if isinstance(stmt, LetStmt):
            local_env[stmt.name] = _infer_expr_type(stmt.expr, local_env, functions)
            continue
        if isinstance(stmt, ReturnStmt):
            expr_type = _infer_expr_type(stmt.expr, local_env, functions)
            if return_type is not None and expr_type is not None and expr_type != return_type:
                raise _error(f"return type mismatch: expected {return_type}, got {expr_type}")
            continue
        if isinstance(stmt, ExprStmt):
            _infer_expr_type(stmt.expr, local_env, functions)
            continue
        if isinstance(stmt, IfStmt):
            condition_type = _infer_expr_type(stmt.condition, local_env, functions)
            if condition_type is not None and condition_type != "bool":
                raise _error("if requires bool condition")
            _typecheck_block(stmt.then_body, dict(local_env), functions, return_type)
            _typecheck_block(stmt.else_body, dict(local_env), functions, return_type)
            continue
        raise _error("unsupported statement during subset typecheck")


def _infer_expr_type(
    expr: Expr,
    env: dict[str, TypeRef | None],
    functions: dict[str, FunctionDef],
) -> TypeRef | None:
    if isinstance(expr, StringLiteral):
        return "string"
    if isinstance(expr, BoolLiteral):
        return "bool"
    if isinstance(expr, IntLiteral):
        return "int"
    if isinstance(expr, Variable):
        return env.get(expr.name)
    if isinstance(expr, Call):
        if expr.callee == "eq":
            if len(expr.args) != 2:
                raise _error("eq expects 2 arguments")
            left = _infer_expr_type(expr.args[0], env, functions)
            right = _infer_expr_type(expr.args[1], env, functions)
            if left is not None and right is not None and left != right:
                raise _error("eq requires matching operand types")
            return "bool"
        signature = BUILTIN_SIGNATURES.get(expr.callee)
        if signature is not None:
            if len(expr.args) != len(signature.arg_types):
                raise _error(f"{expr.callee} expects {len(signature.arg_types)} arguments, got {len(expr.args)}")
            for arg, expected in zip(expr.args, signature.arg_types):
                actual = _infer_expr_type(arg, env, functions)
                if expected is not None and actual is not None and actual != expected:
                    raise _error(f"{expr.callee} expects {expected} argument, got {actual}")
            return signature.return_type
        if expr.callee not in functions:
            raise _error(f"unknown function: {expr.callee}")
        fn = functions[expr.callee]
        if len(expr.args) != len(fn.params):
            raise _error(f"{expr.callee} expects {len(fn.params)} arguments, got {len(expr.args)}")
        for arg, param in zip(expr.args, fn.params):
            actual = _infer_expr_type(arg, env, functions)
            if param.type_ref is not None and actual is not None and actual != param.type_ref:
                raise _error(f"{expr.callee} expects {param.type_ref} for {param.name}, got {actual}")
        return fn.return_type
    raise _error("unsupported expression during subset typecheck")


def _runtime_type_of(value: object) -> TypeRef | None:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, str):
        return "string"
    if value is None:
        return "unit"
    return None


def _error(message: str) -> DiagnosticError:
    return DiagnosticError(
        Diagnostic(
            phase="subset-typecheck",
            code="type_error",
            message=message,
            line=None,
            column=None,
            snippet=None,
        )
    )
