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
        self.parser = Lark(grammar, parser="lalr", propagate_positions=True)
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

    def _extract_node_span(self, node: Any) -> dict[str, int]:
        line: int | None = None
        column: int | None = None
        end_line: int | None = None
        end_column: int | None = None

        if hasattr(node, "meta") and node.meta is not None:
            line = getattr(node.meta, "line", None)
            column = getattr(node.meta, "column", None)
            end_line = getattr(node.meta, "end_line", None)
            end_column = getattr(node.meta, "end_column", None)

        if line is None and hasattr(node, "line"):
            line = getattr(node, "line", None)
            column = getattr(node, "column", None)
            end_line = getattr(node, "end_line", None)
            end_column = getattr(node, "end_column", None)

        if (
            (line is None or column is None)
            and hasattr(node, "children")
            and node.children
        ):
            child_spans = [
                self._extract_node_span(c) for c in node.children if c is not None
            ]
            valid_spans = [s for s in child_spans if s.get("line") is not None]
            if valid_spans:
                line = min(s["line"] for s in valid_spans)
                column = min(s["column"] for s in valid_spans if s["line"] == line)
                end_line = max(s["end_line"] for s in valid_spans)
                end_column = max(
                    s["end_column"] for s in valid_spans if s["end_line"] == end_line
                )

        resolved_line = line if line is not None else 1
        resolved_column = column if column is not None else 1
        resolved_end_line = end_line if end_line is not None else resolved_line
        val_str = str(getattr(node, "value", str(node)))
        resolved_end_column = (
            end_column
            if end_column is not None
            else (resolved_column + max(1, len(val_str)))
        )

        return {
            "line": resolved_line,
            "column": resolved_column,
            "start_line": resolved_line,
            "start_column": resolved_column,
            "end_line": resolved_end_line,
            "end_column": resolved_end_column,
        }

    def _categorize_node(
        self,
        node: Any,
        label: str,
        span: dict[str, int],
        diagnostics: list[CompilerDiagnostic] | None = None,
    ) -> str:
        if getattr(node, "type", "") == "ERROR" or getattr(node, "data", "") == "error":
            return "error"
        if (
            "error" in label.lower()
            or "error" in str(getattr(node, "data", "")).lower()
        ):
            return "error"
        if diagnostics:
            for d in diagnostics:
                if (
                    d.severity == "error"
                    and d.line is not None
                    and d.line == span["line"]
                    and (
                        d.column is None
                        or (span["column"] <= d.column <= span["end_column"])
                    )
                ):
                    return "error"

        node_type = str(getattr(node, "type", "")).upper()
        node_data = str(getattr(node, "data", "")).lower()
        lbl_lower = label.lower()

        if node_type in ("IDENTIFIER", "CNAME") or node_data in (
            "variable",
            "identifier",
            "type_spec",
        ):
            return "identifier"
        if lbl_lower in ("identifier", "variable", "type_spec"):
            return "identifier"

        expr_rules = {
            "expr",
            "comparison",
            "arith_expr",
            "term",
            "atom",
            "add",
            "sub",
            "mul",
            "div",
            "eq",
            "ne",
            "number",
            "boolean",
        }
        if node_data in expr_rules:
            return "expression"
        if node_type in (
            "NUMBER",
            "BOOLEAN",
            "PLUS",
            "MINUS",
            "STAR",
            "SLASH",
            "EQ",
            "NE",
        ):
            return "expression"
        if lbl_lower in expr_rules or label.isdigit() or lbl_lower in ("true", "false"):
            return "expression"

        cf_rules = {
            "start",
            "statement",
            "var_decl",
            "assign_stmt",
            "print_stmt",
            "if_stmt",
            "block",
            "branch",
        }
        if node_data in cf_rules or node_type in (
            "IF",
            "ELSE",
            "VAR",
            "LET",
            "PRINT",
            "BLOCK",
        ):
            return "control_flow"
        if lbl_lower in cf_rules or lbl_lower in ("if", "else"):
            return "control_flow"

        if isinstance(node, str) and node.isidentifier():
            return "identifier"

        return "control_flow"

    def export_cytoscape_json(
        self,
        node: Any,
        parent_id: str | None = None,
        elements: list[dict[str, Any]] | None = None,
        counter: list[int] | None = None,
        mode: str = "ast",
        filter_ast: bool | None = None,
        diagnostics: list[CompilerDiagnostic] | None = None,
    ) -> list[dict[str, Any]]:
        if elements is None:
            elements = []
        if counter is None:
            counter = [0]
        if node is None:
            return elements

        if filter_ast is not None:
            mode = "ast" if filter_ast else "cst"
        mode = mode.lower()

        current_id = str(counter[0])
        counter[0] += 1

        # AST Mode Filtering: collapse trivial wrapper nodes (e.g. number -> 10, variable -> x)
        if mode == "ast" and hasattr(node, "data") and hasattr(node, "children"):
            if (
                node.data in ("number", "boolean", "variable")
                and len(node.children) == 1
            ):
                child = node.children[0]
                child_label = str(getattr(child, "value", child))
                span = self._extract_node_span(child)
                category = (
                    "expression" if node.data in ("number", "boolean") else "identifier"
                )
                if diagnostics:
                    for d in diagnostics:
                        if d.severity == "error" and d.line == span["line"]:
                            category = "error"
                            break

                elements.append(
                    {
                        "data": {
                            "id": current_id,
                            "label": child_label,
                            "category": category,
                            "span": span,
                        }
                    }
                )
                if parent_id is not None:
                    elements.append(
                        {"data": {"source": parent_id, "target": current_id}}
                    )
                return elements

            if node.data == "type_spec" and len(node.children) == 1:
                child = node.children[0]
                child_label = f": {getattr(child, 'value', child)}"
                span = self._extract_node_span(child)
                category = self._categorize_node(child, child_label, span, diagnostics)
                elements.append(
                    {
                        "data": {
                            "id": current_id,
                            "label": child_label,
                            "category": category,
                            "span": span,
                        }
                    }
                )
                if parent_id is not None:
                    elements.append(
                        {"data": {"source": parent_id, "target": current_id}}
                    )
                return elements

        label = node.data if hasattr(node, "data") else str(node)
        span = self._extract_node_span(node)
        category = self._categorize_node(node, str(label), span, diagnostics)

        elements.append(
            {
                "data": {
                    "id": current_id,
                    "label": str(label),
                    "category": category,
                    "span": span,
                }
            }
        )

        if parent_id is not None:
            elements.append({"data": {"source": parent_id, "target": current_id}})

        if hasattr(node, "children"):
            for child in node.children:
                self.export_cytoscape_json(
                    child,
                    parent_id=current_id,
                    elements=elements,
                    counter=counter,
                    mode=mode,
                    filter_ast=filter_ast,
                    diagnostics=diagnostics,
                )

        return elements

    def compile(self, code: str, mode: str = "ast") -> ParseAnalysisResponse:
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
            symbol_table, semantic_diags = self.semantic_analyzer.analyze(tree)
            diagnostics.extend(semantic_diags)
            graph = self.export_cytoscape_json(tree, mode=mode, diagnostics=diagnostics)
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
