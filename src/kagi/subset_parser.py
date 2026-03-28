from __future__ import annotations

from .diagnostics import Diagnostic, DiagnosticError
from .subset_ast import BoolLiteral, Call, Expr, ExprStmt, FunctionDef, IfStmt, IntLiteral, LetStmt, ReturnStmt, Stmt, StringLiteral, SubsetProgram, Variable
from .subset_lexer import Token, tokenize


class Parser:
    def __init__(self, source: str):
        self.source = source
        self.lines = source.splitlines()
        self.tokens = tokenize(source)
        self.index = 0

    def parse_program(self) -> SubsetProgram:
        functions: list[FunctionDef] = []
        while self.peek().kind != "EOF":
            functions.append(self.parse_function())
        return SubsetProgram(functions=functions)

    def parse_function(self) -> FunctionDef:
        self.expect("FN")
        name = self.expect("IDENT").value
        self.expect("LPAREN")
        params: list[str] = []
        if self.peek().kind != "RPAREN":
            params.append(self.expect("IDENT").value)
            while self.match("COMMA"):
                params.append(self.expect("IDENT").value)
        self.expect("RPAREN")
        body = self.parse_block()
        return FunctionDef(name=name, params=params, body=body)

    def parse_block(self) -> list[Stmt]:
        self.expect("LBRACE")
        body: list[Stmt] = []
        while self.peek().kind != "RBRACE":
            body.append(self.parse_stmt())
        self.expect("RBRACE")
        return body

    def parse_stmt(self) -> Stmt:
        token = self.peek()
        if token.kind == "LET":
            self.advance()
            name = self.expect("IDENT").value
            self.expect("EQUAL")
            expr = self.parse_expr()
            self.expect("SEMICOLON")
            return LetStmt(name=name, expr=expr)
        if token.kind == "RETURN":
            self.advance()
            expr = self.parse_expr()
            self.expect("SEMICOLON")
            return ReturnStmt(expr=expr)
        if token.kind == "IF":
            self.advance()
            condition = self.parse_expr()
            then_body = self.parse_block()
            else_body: list[Stmt] = []
            if self.match("ELSE"):
                else_body = self.parse_block()
            return IfStmt(condition=condition, then_body=then_body, else_body=else_body)
        expr = self.parse_expr()
        self.expect("SEMICOLON")
        return ExprStmt(expr=expr)

    def parse_expr(self) -> Expr:
        token = self.peek()
        if token.kind == "STRING":
            self.advance()
            return StringLiteral(token.value)
        if token.kind == "INT":
            self.advance()
            return IntLiteral(int(token.value))
        if token.kind == "TRUE":
            self.advance()
            return BoolLiteral(True)
        if token.kind == "FALSE":
            self.advance()
            return BoolLiteral(False)
        if token.kind == "IDENT":
            self.advance()
            if self.match("LPAREN"):
                args: list[Expr] = []
                if self.peek().kind != "RPAREN":
                    args.append(self.parse_expr())
                    while self.match("COMMA"):
                        args.append(self.parse_expr())
                self.expect("RPAREN")
                return Call(token.value, args)
            return Variable(token.value)
        raise self.error(token, "expected expression", code="expected_expression")

    def peek(self) -> Token:
        return self.tokens[self.index]

    def advance(self) -> Token:
        token = self.tokens[self.index]
        self.index += 1
        return token

    def match(self, kind: str) -> bool:
        if self.peek().kind == kind:
            self.advance()
            return True
        return False

    def expect(self, kind: str) -> Token:
        token = self.peek()
        if token.kind != kind:
            raise self.error(token, f"expected {kind}, got {token.kind}", code="unexpected_token")
        return self.advance()

    def error(self, token: Token, message: str, *, code: str) -> DiagnosticError:
        return DiagnosticError(
            Diagnostic(
                phase="subset-parse",
                code=code,
                message=message,
                line=token.line,
                column=token.column,
                snippet=token.snippet,
            )
        )


def parse_subset_program(source: str) -> SubsetProgram:
    parser = Parser(source)
    program = parser.parse_program()
    parser.expect("EOF")
    return program
