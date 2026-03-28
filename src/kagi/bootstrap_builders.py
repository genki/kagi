from __future__ import annotations

import json

from .diagnostics import DiagnosticError
from .hir import hir_program_v1_to_json, lower_surface_program_to_hir_v1
from .surface_ast import parse_surface_program_v1

def builtin_print_ast(text: object) -> str:
    if not isinstance(text, str):
        text = str(text)
    return json.dumps(
        {"kind": "print", "expr": {"kind": "string", "value": text}},
        ensure_ascii=False,
        separators=(",", ":"),
    )


def builtin_program_ast(text: object) -> str:
    if not isinstance(text, str):
        text = str(text)
    return json.dumps(
        {
            "kind": "program",
            "functions": [],
            "statements": [{"kind": "print", "expr": {"kind": "string", "value": text}}],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def builtin_program_print_concat_ast(left_text: object, right_text: object) -> str:
    if not isinstance(left_text, str):
        left_text = str(left_text)
    if not isinstance(right_text, str):
        right_text = str(right_text)
    return json.dumps(
        {
            "kind": "program",
            "functions": [],
            "statements": [
                {
                    "kind": "print",
                    "expr": {
                        "kind": "concat",
                        "left": {"kind": "string", "value": left_text},
                        "right": {"kind": "string", "value": right_text},
                    },
                }
            ],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def builtin_program_let_print_ast(name: object, text: object) -> str:
    if not isinstance(name, str):
        name = str(name)
    if not isinstance(text, str):
        text = str(text)
    return json.dumps(
        {
            "kind": "program",
            "functions": [],
            "statements": [
                {"kind": "let", "name": name, "expr": {"kind": "string", "value": text}},
                {"kind": "print", "expr": {"kind": "var", "name": name}},
            ],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def builtin_program_let_concat_print_ast(name: object, left_text: object, right_text: object) -> str:
    if not isinstance(name, str):
        name = str(name)
    if not isinstance(left_text, str):
        left_text = str(left_text)
    if not isinstance(right_text, str):
        right_text = str(right_text)
    return json.dumps(
        {
            "kind": "program",
            "functions": [],
            "statements": [
                {
                    "kind": "let",
                    "name": name,
                    "expr": {
                        "kind": "concat",
                        "left": {"kind": "string", "value": left_text},
                        "right": {"kind": "string", "value": right_text},
                    },
                },
                {"kind": "print", "expr": {"kind": "var", "name": name}},
            ],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def builtin_program_single_arg_fn_call_ast(fn_name: object, param_name: object, arg_text: object, suffix_text: object) -> str:
    if not isinstance(fn_name, str):
        fn_name = str(fn_name)
    if not isinstance(param_name, str):
        param_name = str(param_name)
    if not isinstance(arg_text, str):
        arg_text = str(arg_text)
    if not isinstance(suffix_text, str):
        suffix_text = str(suffix_text)
    return json.dumps(
        {
            "kind": "program",
            "functions": [
                {
                    "kind": "fn",
                    "name": fn_name,
                    "params": [param_name],
                    "body": [
                        {
                            "kind": "print",
                            "expr": {
                                "kind": "concat",
                                "left": {"kind": "var", "name": param_name},
                                "right": {"kind": "string", "value": suffix_text},
                            },
                        }
                    ],
                }
            ],
            "statements": [
                {"kind": "call", "name": fn_name, "args": [{"kind": "string", "value": arg_text}]}
            ],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def builtin_program_two_prints_ast(first_text: object, second_text: object) -> str:
    if not isinstance(first_text, str):
        first_text = str(first_text)
    if not isinstance(second_text, str):
        second_text = str(second_text)
    return json.dumps(
        {
            "kind": "program",
            "functions": [],
            "statements": [
                {"kind": "print", "expr": {"kind": "string", "value": first_text}},
                {"kind": "print", "expr": {"kind": "string", "value": second_text}},
            ],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def builtin_program_zero_arg_fn_call_ast(fn_name: object, var_name: object, left_text: object, right_text: object) -> str:
    if not isinstance(fn_name, str):
        fn_name = str(fn_name)
    if not isinstance(var_name, str):
        var_name = str(var_name)
    if not isinstance(left_text, str):
        left_text = str(left_text)
    if not isinstance(right_text, str):
        right_text = str(right_text)
    return json.dumps(
        {
            "kind": "program",
            "functions": [
                {
                    "kind": "fn",
                    "name": fn_name,
                    "params": [],
                    "body": [
                        {
                            "kind": "let",
                            "name": var_name,
                            "expr": {
                                "kind": "concat",
                                "left": {"kind": "string", "value": left_text},
                                "right": {"kind": "string", "value": right_text},
                            },
                        },
                        {"kind": "print", "expr": {"kind": "var", "name": var_name}},
                    ],
                }
            ],
            "statements": [{"kind": "call", "name": fn_name, "args": []}],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def builtin_program_if_expr_print_ast(greeting_name: object, left_text: object, right_text: object, enabled_name: object, expected_text: object, disabled_text: object) -> str:
    if not isinstance(greeting_name, str):
        greeting_name = str(greeting_name)
    if not isinstance(left_text, str):
        left_text = str(left_text)
    if not isinstance(right_text, str):
        right_text = str(right_text)
    if not isinstance(enabled_name, str):
        enabled_name = str(enabled_name)
    if not isinstance(expected_text, str):
        expected_text = str(expected_text)
    if not isinstance(disabled_text, str):
        disabled_text = str(disabled_text)
    return json.dumps(
        {
            "kind": "program",
            "functions": [],
            "statements": [
                {
                    "kind": "let",
                    "name": greeting_name,
                    "expr": {
                        "kind": "concat",
                        "left": {"kind": "string", "value": left_text},
                        "right": {"kind": "string", "value": right_text},
                    },
                },
                {
                    "kind": "let",
                    "name": enabled_name,
                    "expr": {
                        "kind": "eq",
                        "left": {"kind": "var", "name": greeting_name},
                        "right": {"kind": "string", "value": expected_text},
                    },
                },
                {
                    "kind": "print",
                    "expr": {
                        "kind": "if",
                        "condition": {"kind": "var", "name": enabled_name},
                        "then": {"kind": "var", "name": greeting_name},
                        "else": {"kind": "string", "value": disabled_text},
                    },
                },
            ],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def builtin_program_if_stmt_ast(greeting_name: object, left_text: object, right_text: object, enabled_name: object, expected_text: object, disabled_text: object) -> str:
    if not isinstance(greeting_name, str):
        greeting_name = str(greeting_name)
    if not isinstance(left_text, str):
        left_text = str(left_text)
    if not isinstance(right_text, str):
        right_text = str(right_text)
    if not isinstance(enabled_name, str):
        enabled_name = str(enabled_name)
    if not isinstance(expected_text, str):
        expected_text = str(expected_text)
    if not isinstance(disabled_text, str):
        disabled_text = str(disabled_text)
    return json.dumps(
        {
            "kind": "program",
            "functions": [],
            "statements": [
                {
                    "kind": "let",
                    "name": greeting_name,
                    "expr": {
                        "kind": "concat",
                        "left": {"kind": "string", "value": left_text},
                        "right": {"kind": "string", "value": right_text},
                    },
                },
                {
                    "kind": "let",
                    "name": enabled_name,
                    "expr": {
                        "kind": "eq",
                        "left": {"kind": "var", "name": greeting_name},
                        "right": {"kind": "string", "value": expected_text},
                    },
                },
                {
                    "kind": "if_stmt",
                    "condition": {"kind": "var", "name": enabled_name},
                    "then_body": [{"kind": "print", "expr": {"kind": "var", "name": greeting_name}}],
                    "else_body": [{"kind": "print", "expr": {"kind": "string", "value": disabled_text}}],
                },
            ],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def builtin_print_many_artifact(text: object) -> str:
    if not isinstance(text, str):
        text = str(text)
    return json.dumps({"kind": "print_many", "texts": [text]}, ensure_ascii=False, separators=(",", ":"))


def builtin_program_text(ast: object) -> str:
    if not isinstance(ast, str):
        return ""
    try:
        payload = json.loads(ast)
    except json.JSONDecodeError:
        return ""
    if not isinstance(payload, dict) or payload.get("kind") != "program":
        return ""
    statements = payload.get("statements")
    if not isinstance(statements, list) or len(statements) != 1:
        return ""
    stmt = statements[0]
    if not isinstance(stmt, dict) or stmt.get("kind") != "print":
        return ""
    expr = stmt.get("expr")
    if not isinstance(expr, dict) or expr.get("kind") != "string":
        return ""
    text = expr.get("value")
    return text if isinstance(text, str) else ""


def builtin_program_ast_to_hir(ast: object) -> str:
    if not isinstance(ast, str):
        return ""
    try:
        surface = parse_surface_program_v1(ast)
        hir = lower_surface_program_to_hir_v1(surface)
    except DiagnosticError:
        return ""
    return hir_program_v1_to_json(hir)


BOOTSTRAP_BUILTINS = {
    "print_ast": builtin_print_ast,
    "print_many_artifact": builtin_print_many_artifact,
    "program_ast": builtin_program_ast,
    "program_ast_to_hir": builtin_program_ast_to_hir,
    "program_if_expr_print_ast": builtin_program_if_expr_print_ast,
    "program_if_stmt_ast": builtin_program_if_stmt_ast,
    "program_print_concat_ast": builtin_program_print_concat_ast,
    "program_let_concat_print_ast": builtin_program_let_concat_print_ast,
    "program_single_arg_fn_call_ast": builtin_program_single_arg_fn_call_ast,
    "program_let_print_ast": builtin_program_let_print_ast,
    "program_two_prints_ast": builtin_program_two_prints_ast,
    "program_text": builtin_program_text,
    "program_zero_arg_fn_call_ast": builtin_program_zero_arg_fn_call_ast,
}
