from __future__ import annotations

from typing import Any

from lark import Lark, Transformer
from lark.exceptions import (
    LarkError,
    ParseError,
    UnexpectedCharacters,
    UnexpectedEOF,
    UnexpectedToken,
)

from py_ast.core.schemas import (
    CompilerDiagnostic,
    ParseAnalysisResponse,
    SourceSpan,
    TokenDTO,
)
from py_ast.core.semantic import SemanticAnalyzer

# Lark uses UnexpectedToken for unexpected token errors; alias for compatibility
UnexpectedTokens = UnexpectedToken

EBNF_GRAMMAR = """
    ?start: statement+

    ?statement: var_decl
             | assign_stmt
             | print_stmt
             | if_stmt
             | block

    block: "{" statement* "}"

    var_decl: ("var" | "let") IDENTIFIER (type_spec)? ("=" expr)? ";"
    type_spec: ":" IDENTIFIER
    assign_stmt: IDENTIFIER "=" expr ";"
    print_stmt: "print" "(" expr ")" ";"
    if_stmt: "if" "(" expr ")" block ("else" block)?

    ?expr: comparison

    ?comparison: arith_expr
               | comparison "==" arith_expr -> eq
               | comparison "!=" arith_expr -> ne

    ?arith_expr: term
               | arith_expr "+" term -> add
               | arith_expr "-" term -> sub

    ?term: atom
         | term "*" atom -> mul
         | term "/" atom -> div

    ?atom: NUMBER           -> number
         | BOOLEAN          -> boolean
         | IDENTIFIER       -> variable
         | "(" expr ")"

    BOOLEAN.2: "true" | "false" | "True" | "False"
    %import common.CNAME -> IDENTIFIER
    %import common.NUMBER
    %import common.WS
    %ignore WS
"""


class ASTToPythonTransformer(Transformer):
    def number(self, args: list[Any]) -> str:
        return str(args[0].value)

    def boolean(self, args: list[Any]) -> str:
        return str(args[0].value).capitalize()

    def variable(self, args: list[Any]) -> str:
        return str(args[0].value)

    def add(self, args: list[Any]) -> str:
        return f"({args[0]} + {args[1]})"

    def sub(self, args: list[Any]) -> str:
        return f"({args[0]} - {args[1]})"

    def mul(self, args: list[Any]) -> str:
        return f"({args[0]} * {args[1]})"

    def div(self, args: list[Any]) -> str:
        return f"({args[0]} / {args[1]})"

    def eq(self, args: list[Any]) -> str:
        return f"({args[0]} == {args[1]})"

    def ne(self, args: list[Any]) -> str:
        return f"({args[0]} != {args[1]})"

    def type_spec(self, args: list[Any]) -> str:
        return str(args[0].value)

    def var_decl(self, args: list[Any]) -> str:
        name = str(args[0].value)
        if len(args) == 1:
            return f"{name} = None"
        if len(args) == 2:
            return f"{name} = {args[1]}"
        return f"{name} = {args[2]}"

    def assign_stmt(self, args: list[Any]) -> str:
        return f"{args[0].value} = {args[1]}"

    def print_stmt(self, args: list[Any]) -> str:
        return f"print({args[0]})"

    def block(self, args: list[Any]) -> str:
        return "\n".join(str(arg) for arg in args if arg)

    def if_stmt(self, args: list[Any]) -> str:
        cond = args[0]
        then_block = str(args[1])
        indented_then = (
            "\n".join(f"    {line}" for line in then_block.splitlines())
            if then_block.strip()
            else "    pass"
        )
        if len(args) > 2:
            else_block = str(args[2])
            indented_else = (
                "\n".join(f"    {line}" for line in else_block.splitlines())
                if else_block.strip()
                else "    pass"
            )
            return f"if {cond}:\n{indented_then}\nelse:\n{indented_else}"
        return f"if {cond}:\n{indented_then}"

    def start(self, args: list[Any]) -> str:
        return "\n".join(str(arg) for arg in args if arg)


class CompilerPipeline:
    def __init__(self, grammar: str = EBNF_GRAMMAR) -> None:
        self.parser = Lark(grammar, parser="lalr")
        self.transformer = ASTToPythonTransformer()
        self.semantic_analyzer = SemanticAnalyzer()

    def extract_tokens(self, code: str) -> list[TokenDTO]:
        tokens: list[TokenDTO] = []
        try:
            for t in self.parser.lex(code):
                span = SourceSpan(
                    start_line=t.line or 1,
                    start_column=t.column or 1,
                    end_line=t.end_line,
                    end_column=t.end_column,
                )
                tokens.append(
                    TokenDTO(
                        type=t.type,
                        value=str(t.value),
                        line=t.line or 1,
                        column=t.column or 1,
                        span=span,
                    )
                )
        except (UnexpectedCharacters, LarkError):
            pass
        return tokens

    def safe_parse(self, code: str) -> tuple[Any | None, list[CompilerDiagnostic]]:
        diagnostics: list[CompilerDiagnostic] = []
        try:
            tree = self.parser.parse(code)
            return tree, diagnostics
        except UnexpectedCharacters as exc:
            line = getattr(exc, "line", None)
            column = getattr(exc, "column", None)
            span = (
                SourceSpan(start_line=line or 1, start_column=column or 1)
                if (line is not None and column is not None)
                else None
            )
            diagnostics.append(
                CompilerDiagnostic(
                    message=str(exc).strip(),
                    severity="error",
                    line=line,
                    column=column,
                    span=span,
                    code="UNEXPECTED_CHARACTERS",
                )
            )
            return None, diagnostics
        except (UnexpectedToken, UnexpectedEOF) as exc:
            line = getattr(exc, "line", None)
            column = getattr(exc, "column", None)
            span = (
                SourceSpan(start_line=line or 1, start_column=column or 1)
                if (line is not None and column is not None)
                else None
            )
            diagnostics.append(
                CompilerDiagnostic(
                    message=str(exc).strip(),
                    severity="error",
                    line=line,
                    column=column,
                    span=span,
                    code="UNEXPECTED_TOKEN",
                )
            )
            return None, diagnostics
        except (ParseError, LarkError) as exc:
            line = getattr(exc, "line", None)
            column = getattr(exc, "column", None)
            span = (
                SourceSpan(start_line=line or 1, start_column=column or 1)
                if (line is not None and column is not None)
                else None
            )
            diagnostics.append(
                CompilerDiagnostic(
                    message=str(exc).strip(),
                    severity="error",
                    line=line,
                    column=column,
                    span=span,
                    code="PARSE_ERROR",
                )
            )
            return None, diagnostics

    def parse_to_tree(self, code: str) -> Any:
        return self.parser.parse(code)

    def generate_python(self, parse_tree: Any) -> str:
        return self.transformer.transform(parse_tree)

    def export_cytoscape_json(
        self,
        node: Any,
        parent_id: str | None = None,
        elements: list[dict[str, Any]] | None = None,
        counter: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        if elements is None:
            elements = []
        if counter is None:
            counter = [0]
        if node is None:
            return elements

        current_id = str(counter[0])
        counter[0] += 1

        label = node.data if hasattr(node, "data") else str(node)
        elements.append({"data": {"id": current_id, "label": str(label)}})

        if parent_id is not None:
            elements.append({"data": {"source": parent_id, "target": current_id}})

        if hasattr(node, "children"):
            for child in node.children:
                self.export_cytoscape_json(child, current_id, elements, counter)

        return elements

    def compile(self, code: str) -> ParseAnalysisResponse:
        tokens = self.extract_tokens(code)
        tree, diagnostics = self.safe_parse(code)

        if tree is not None:
            try:
                python_code = self.generate_python(tree)
            except Exception as exc:  # noqa: BLE001
                python_code = ""
                diagnostics.append(
                    CompilerDiagnostic(
                        message=f"Code generation error: {exc}",
                        severity="error",
                        code="CODEGEN_ERROR",
                    )
                )
            graph = self.export_cytoscape_json(tree)
            symbol_table, semantic_diags = self.semantic_analyzer.analyze(tree)
            diagnostics.extend(semantic_diags)
            return ParseAnalysisResponse(
                tokens=tokens,
                generated_python=python_code,
                cytoscape_graph=graph,
                symbol_table=symbol_table,
                diagnostics=diagnostics,
            )

        return ParseAnalysisResponse(
            tokens=tokens,
            generated_python="",
            cytoscape_graph=[],
            symbol_table=None,
            diagnostics=diagnostics,
        )
