from __future__ import annotations

from typing import Any

from lark import Token, Tree

from py_ast.core.schemas import (
    CompilerDiagnostic,
    SourceSpan,
    SymbolDTO,
    SymbolTableDTO,
)


class SymbolScope:
    def __init__(
        self,
        name: str = "global",
        level: int = 0,
        parent: SymbolScope | None = None,
    ) -> None:
        self.name = name
        self.level = level
        self.parent = parent
        self.symbols: dict[str, SymbolDTO] = {}
        self.children: list[SymbolScope] = []

    def define(
        self,
        name: str,
        symbol_type: str = "variable",
        span: SourceSpan | None = None,
        line: int | None = None,
        column: int | None = None,
    ) -> SymbolDTO:
        symbol = SymbolDTO(
            name=name,
            symbol_type=symbol_type,
            scope_level=self.level,
            span=span,
            line=line,
            column=column,
        )
        self.symbols[name] = symbol
        return symbol

    def lookup_current(self, name: str) -> SymbolDTO | None:
        return self.symbols.get(name)

    def resolve(self, name: str) -> SymbolDTO | None:
        if name in self.symbols:
            return self.symbols[name]
        if self.parent is not None:
            return self.parent.resolve(name)
        return None

    def create_child_scope(self, name: str = "block") -> SymbolScope:
        child = SymbolScope(name=name, level=self.level + 1, parent=self)
        self.children.append(child)
        return child

    def to_dto(self) -> SymbolTableDTO:
        return SymbolTableDTO(
            scope_name=self.name,
            scope_level=self.level,
            parent_scope=self.parent.name if self.parent else None,
            symbols=dict(self.symbols),
            children=[child.to_dto() for child in self.children],
        )

    def __contains__(self, name: object) -> bool:
        if isinstance(name, str):
            return self.resolve(name) is not None
        return False

    def __getitem__(self, name: str) -> SymbolDTO:
        symbol = self.resolve(name)
        if symbol is None:
            raise KeyError(name)
        return symbol


def _token_value(node: Any) -> str:
    if isinstance(node, Token):
        return str(node.value)
    return str(getattr(node, "value", node))


class SemanticAnalyzer:
    def __init__(self) -> None:
        self.global_scope = SymbolScope(name="global", level=0)
        self.current_scope = self.global_scope
        self.diagnostics: list[CompilerDiagnostic] = []

    def analyze(self, tree: Any) -> tuple[SymbolTableDTO, list[CompilerDiagnostic]]:
        self.global_scope = SymbolScope(name="global", level=0)
        self.current_scope = self.global_scope
        self.diagnostics = []

        if tree is not None:
            self._visit(tree)

        return self.global_scope.to_dto(), self.diagnostics

    def _extract_span(self, token_or_tree: Any) -> SourceSpan | None:
        line = getattr(token_or_tree, "line", None)
        column = getattr(token_or_tree, "column", None)
        if line is not None and column is not None:
            return SourceSpan(
                start_line=line,
                start_column=column,
                end_line=getattr(token_or_tree, "end_line", None),
                end_column=getattr(token_or_tree, "end_column", None),
            )
        return None

    def _visit(self, node: Any) -> None:
        if isinstance(node, Tree):
            handler = getattr(self, f"_visit_{node.data}", self._visit_generic)
            handler(node)
        elif isinstance(node, Token):
            pass

    def _visit_generic(self, tree: Tree) -> None:
        for child in tree.children:
            self._visit(child)

    def _visit_var_decl(self, tree: Tree) -> None:
        name_tok = tree.children[0]
        var_name = _token_value(name_tok)
        span = self._extract_span(name_tok)
        line = getattr(name_tok, "line", None)
        column = getattr(name_tok, "column", None)
        var_type = "variable"
        expr_node = None

        for child in tree.children[1:]:
            if isinstance(child, Tree) and child.data == "type_spec":
                var_type = _token_value(child.children[0])
            else:
                expr_node = child

        if expr_node is not None:
            self._visit(expr_node)

        if self.current_scope.lookup_current(var_name) is not None:
            self.diagnostics.append(
                CompilerDiagnostic(
                    message=f"Duplicate variable declaration '{var_name}' in current scope",
                    severity="error",
                    line=line,
                    column=column,
                    span=span,
                    code="DUPLICATE_DECLARATION",
                )
            )

        self.current_scope.define(
            name=var_name,
            symbol_type=var_type,
            span=span,
            line=line,
            column=column,
        )

    def _visit_assign_stmt(self, tree: Tree) -> None:
        name_tok = tree.children[0]
        var_name = _token_value(name_tok)
        expr_node = tree.children[1]

        self._visit(expr_node)

        if self.current_scope.resolve(var_name) is None:
            span = self._extract_span(name_tok)
            line = getattr(name_tok, "line", None)
            column = getattr(name_tok, "column", None)
            self.diagnostics.append(
                CompilerDiagnostic(
                    message=f"Unresolved identifier '{var_name}' in assignment",
                    severity="error",
                    line=line,
                    column=column,
                    span=span,
                    code="UNRESOLVED_IDENTIFIER",
                )
            )
            self.current_scope.define(
                name=var_name,
                symbol_type="unresolved",
                span=span,
                line=line,
                column=column,
            )

    def _visit_variable(self, tree: Tree) -> None:
        name_tok = tree.children[0]
        var_name = _token_value(name_tok)

        if self.current_scope.resolve(var_name) is None:
            span = self._extract_span(name_tok)
            line = getattr(name_tok, "line", None)
            column = getattr(name_tok, "column", None)
            self.diagnostics.append(
                CompilerDiagnostic(
                    message=f"Unresolved identifier '{var_name}'",
                    severity="error",
                    line=line,
                    column=column,
                    span=span,
                    code="UNRESOLVED_IDENTIFIER",
                )
            )

    def _visit_if_stmt(self, tree: Tree) -> None:
        # 1. Condition in current scope
        self._visit(tree.children[0])

        # 2. Then branch block
        then_block = tree.children[1]
        then_scope = self.current_scope.create_child_scope(name="if_branch")
        prev_scope = self.current_scope
        self.current_scope = then_scope
        try:
            for stmt in then_block.children:
                self._visit(stmt)
        finally:
            self.current_scope = prev_scope

        # 3. Else branch block if present
        if len(tree.children) > 2:
            else_block = tree.children[2]
            else_scope = self.current_scope.create_child_scope(name="else_branch")
            self.current_scope = else_scope
            try:
                for stmt in else_block.children:
                    self._visit(stmt)
            finally:
                self.current_scope = prev_scope

    def _visit_block(self, tree: Tree) -> None:
        block_scope = self.current_scope.create_child_scope(name="block")
        prev_scope = self.current_scope
        self.current_scope = block_scope
        try:
            for stmt in tree.children:
                self._visit(stmt)
        finally:
            self.current_scope = prev_scope
