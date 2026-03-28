from __future__ import annotations

from dataclasses import dataclass

from .diagnostics import Diagnostic, DiagnosticError


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    line: int
    column: int
    snippet: str


KEYWORDS = {
    "fn": "FN",
    "let": "LET",
    "return": "RETURN",
    "if": "IF",
    "else": "ELSE",
    "true": "TRUE",
    "false": "FALSE",
}


def tokenize(source: str) -> list[Token]:
    tokens: list[Token] = []
    lines = source.splitlines()
    line = 1
    column = 1
    index = 0

    def snippet_for(line_no: int) -> str:
        if 1 <= line_no <= len(lines):
            return lines[line_no - 1]
        return ""

    while index < len(source):
        ch = source[index]
        if ch in " \t\r":
            index += 1
            column += 1
            continue
        if ch == "\n":
            index += 1
            line += 1
            column = 1
            continue
        if ch == "#":
            while index < len(source) and source[index] != "\n":
                index += 1
                column += 1
            continue
        if ch.isalpha() or ch == "_":
            start = index
            start_col = column
            while index < len(source) and (source[index].isalnum() or source[index] == "_"):
                index += 1
                column += 1
            value = source[start:index]
            tokens.append(Token(KEYWORDS.get(value, "IDENT"), value, line, start_col, snippet_for(line)))
            continue
        if ch.isdigit():
            start = index
            start_col = column
            while index < len(source) and source[index].isdigit():
                index += 1
                column += 1
            tokens.append(Token("INT", source[start:index], line, start_col, snippet_for(line)))
            continue
        if ch == '"':
            start_col = column
            index += 1
            column += 1
            chars: list[str] = []
            while index < len(source) and source[index] != '"':
                if source[index] == "\\" and index + 1 < len(source):
                    escape = source[index + 1]
                    mapping = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}
                    chars.append(mapping.get(escape, escape))
                    index += 2
                    column += 2
                    continue
                chars.append(source[index])
                index += 1
                column += 1
            if index >= len(source):
                raise DiagnosticError(
                    Diagnostic(
                        phase="subset-parse",
                        code="unterminated_string",
                        message="unterminated string literal",
                        line=line,
                        column=start_col,
                        snippet=snippet_for(line),
                    )
                )
            index += 1
            column += 1
            tokens.append(Token("STRING", "".join(chars), line, start_col, snippet_for(line)))
            continue
        single_tokens = {
            "(": "LPAREN",
            ")": "RPAREN",
            "{": "LBRACE",
            "}": "RBRACE",
            ",": "COMMA",
            ";": "SEMICOLON",
            "=": "EQUAL",
        }
        if ch in single_tokens:
            tokens.append(Token(single_tokens[ch], ch, line, column, snippet_for(line)))
            index += 1
            column += 1
            continue
        raise DiagnosticError(
            Diagnostic(
                phase="subset-parse",
                code="invalid_character",
                message=f"invalid character: {ch}",
                line=line,
                column=column,
                snippet=snippet_for(line),
            )
        )

    tokens.append(Token("EOF", "", line, column, snippet_for(line)))
    return tokens
