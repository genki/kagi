from .subset_ast import (
    BoolLiteral,
    Call,
    Expr,
    ExprStmt,
    FunctionDef,
    IfStmt,
    IntLiteral,
    LetStmt,
    ParamDef,
    ReturnSignal,
    ReturnStmt,
    Stmt,
    StringLiteral,
    SubsetProgram,
    Variable,
)
from .subset_builtins import (
    CORE_BUILTINS,
    builtin_after_substring,
    builtin_before_substring,
    builtin_concat,
    builtin_ends_with,
    builtin_eq,
    builtin_extract_quoted,
    builtin_is_identifier,
    builtin_line_at,
    builtin_line_count,
    builtin_starts_with,
    builtin_trim,
    intrinsic_after_substring,
    intrinsic_before_substring,
    intrinsic_concat,
    intrinsic_ends_with,
    intrinsic_eq,
    intrinsic_extract_quoted,
    intrinsic_is_identifier,
    intrinsic_line_at,
    intrinsic_line_count,
    intrinsic_starts_with,
    intrinsic_trim,
)
from .bootstrap_builders import (
    BOOTSTRAP_BUILTINS,
    builtin_print_ast,
    builtin_print_many_artifact,
    builtin_program_ast,
    builtin_program_if_expr_print_ast,
    builtin_program_if_stmt_ast,
    builtin_program_let_concat_print_ast,
    builtin_program_let_print_ast,
    builtin_program_print_concat_ast,
    builtin_program_single_arg_fn_call_ast,
    builtin_program_text,
    builtin_program_two_prints_ast,
    builtin_program_zero_arg_fn_call_ast,
)
from .subset_eval import (
    BUILTINS,
    eval_block,
    eval_expr,
    eval_function,
    eval_stmt,
    run_subset_program,
    run_subset_program_via_kir,
    truthy,
)
from .subset_typecheck import SubsetTypecheckResultV0, typecheck_subset_program_v0


def tokenize(source: str):
    from .subset_lexer import tokenize as _tokenize

    return _tokenize(source)


def parse_subset_program(source: str):
    from .subset_parser import parse_subset_program as _parse_subset_program

    return _parse_subset_program(source)


def __getattr__(name: str):
    if name in {"KEYWORDS", "Token"}:
        from .subset_lexer import KEYWORDS, Token

        return {"KEYWORDS": KEYWORDS, "Token": Token}[name]
    if name == "Parser":
        from .subset_parser import Parser

        return Parser
    raise AttributeError(name)
