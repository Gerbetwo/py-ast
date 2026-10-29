from __future__ import annotations

import copy
from typing import Any

from lark import Token, Transformer, Tree

# Operator mappings for binary arithmetic and comparison expressions
VALID_OPERATORS: dict[str, str] = {
    "+": "add",
    "add": "add",
    "-": "sub",
    "sub": "sub",
    "*": "mul",
    "mul": "mul",
    "/": "div",
    "div": "div",
    "==": "eq",
    "eq": "eq",
    "!=": "ne",
    "ne": "ne",
}

RESERVED_KEYWORDS: set[str] = {
    "var",
    "let",
    "if",
    "else",
    "print",
    "true",
    "false",
    "True",
    "False",
}


class ExprRepresentation:
    """Helper to represent expressions with operator precedence for clean parenthesis handling."""

    def __init__(self, text: str, precedence: int) -> None:
        self.text = text
        self.precedence = precedence

    def __str__(self) -> str:
        return self.text


def _wrap_operand(operand: Any, min_precedence: int, is_right: bool = False) -> str:
    """Wrap child expression in parentheses if its precedence requires it."""
    if isinstance(operand, ExprRepresentation):
        if operand.precedence < min_precedence or (
            is_right and operand.precedence == min_precedence
        ):
            return f"({operand.text})"
        return operand.text
    return str(operand)


class SourceRegenerator(Transformer):
    """Lark Transformer to regenerate clean DSL source strings from parse trees."""

    def number(self, args: list[Any]) -> ExprRepresentation:
        return ExprRepresentation(str(args[0].value), 4)

    def boolean(self, args: list[Any]) -> ExprRepresentation:
        val = str(args[0].value).lower()
        return ExprRepresentation(val, 4)

    def variable(self, args: list[Any]) -> ExprRepresentation:
        return ExprRepresentation(str(args[0].value), 4)

    def add(self, args: list[Any]) -> ExprRepresentation:
        return ExprRepresentation(
            f"{_wrap_operand(args[0], 2)} + {_wrap_operand(args[1], 2)}", 2
        )

    def sub(self, args: list[Any]) -> ExprRepresentation:
        return ExprRepresentation(
            f"{_wrap_operand(args[0], 2)} - {_wrap_operand(args[1], 2, is_right=True)}",
            2,
        )

    def mul(self, args: list[Any]) -> ExprRepresentation:
        return ExprRepresentation(
            f"{_wrap_operand(args[0], 3)} * {_wrap_operand(args[1], 3)}", 3
        )

    def div(self, args: list[Any]) -> ExprRepresentation:
        return ExprRepresentation(
            f"{_wrap_operand(args[0], 3)} / {_wrap_operand(args[1], 3, is_right=True)}",
            3,
        )

    def eq(self, args: list[Any]) -> ExprRepresentation:
        return ExprRepresentation(
            f"{_wrap_operand(args[0], 1)} == {_wrap_operand(args[1], 1)}", 1
        )

    def ne(self, args: list[Any]) -> ExprRepresentation:
        return ExprRepresentation(
            f"{_wrap_operand(args[0], 1)} != {_wrap_operand(args[1], 1)}", 1
        )

    def type_spec(self, args: list[Any]) -> str:
        return f": {args[0].value}"

    def var_decl(self, args: list[Any]) -> str:
        name = str(args[0].value)
        if len(args) == 1:
            return f"var {name};"
        if len(args) == 2:
            if isinstance(args[1], str) and args[1].startswith(":"):
                return f"var {name}{args[1]};"
            return f"var {name} = {args[1]};"
        return f"var {name}{args[1]} = {args[2]};"

    def assign_stmt(self, args: list[Any]) -> str:
        return f"{args[0].value} = {args[1]};"

    def print_stmt(self, args: list[Any]) -> str:
        return f"print({args[0]});"

    def block(self, args: list[Any]) -> str:
        stmts = [str(a) for a in args if a]
        if not stmts:
            return "{}"
        inner = "\n".join(f"    {line}" for s in stmts for line in s.splitlines())
        return f"{{\n{inner}\n}}"

    def if_stmt(self, args: list[Any]) -> str:
        cond = str(args[0])
        then_block = str(args[1])
        if len(args) > 2:
            else_block = str(args[2])
            return f"if ({cond}) {then_block} else {else_block}"
        return f"if ({cond}) {then_block}"

    def start(self, args: list[Any]) -> str:
        return "\n".join(str(a) for a in args if a)

    def __default__(self, data: str, children: list[Any], meta: Any) -> Any:
        return "\n".join(str(c) for c in children if c)


class CodeUnparser:
    """Unparses Lark parse trees back into valid source code strings and synthesized Python code."""

    def __init__(self) -> None:
        self.regenerator = SourceRegenerator()

    def regenerate_source(self, parse_tree: Any) -> str:
        """Converts mutated or parsed Lark trees back into valid source strings."""
        if parse_tree is None:
            return ""
        if isinstance(parse_tree, Token):
            return str(parse_tree.value)
        result = self.regenerator.transform(parse_tree)
        return str(result).strip()

    def regenerate_python(self, parse_tree: Any) -> str:
        """Synthesizes high-level Python code from a Lark parse tree."""
        if parse_tree is None:
            return ""
        from py_ast.core.compiler import ASTToPythonTransformer

        transformer = ASTToPythonTransformer()
        return str(transformer.transform(parse_tree)).strip()


def _index_tree_nodes(
    node: Any,
    counter: list[int] | None = None,
    mode: str = "ast",
    parent: Tree | None = None,
    child_index: int | None = None,
) -> dict[str, tuple[Any, Tree | None, int | None]]:
    """Traverses tree in identical pre-order sequence to CompilerPipeline.export_cytoscape_json."""
    if counter is None:
        counter = [0]
    if node is None:
        return {}

    mode = mode.lower()
    current_id = str(counter[0])
    counter[0] += 1
    mapping: dict[str, tuple[Any, Tree | None, int | None]] = {}

    if mode == "ast" and hasattr(node, "data") and hasattr(node, "children"):
        if node.data in ("number", "boolean", "variable") and len(node.children) == 1:
            mapping[current_id] = (node, parent, child_index)
            return mapping
        if node.data == "type_spec" and len(node.children) == 1:
            mapping[current_id] = (node, parent, child_index)
            return mapping

    mapping[current_id] = (node, parent, child_index)
    if hasattr(node, "children"):
        for idx, child in enumerate(node.children):
            mapping.update(
                _index_tree_nodes(
                    child,
                    counter=counter,
                    mode=mode,
                    parent=node,
                    child_index=idx,
                )
            )
    return mapping


class ASTNodeMutator(Transformer):
    """Lark Transformer to mutate target node values or operators within the Lark parse tree."""

    def __init__(
        self,
        node_id: str | None = None,
        new_value: str | None = None,
        mode: str = "ast",
        target_id: str | None = None,
    ) -> None:
        super().__init__(visit_tokens=True)
        self.node_id = node_id if node_id is not None else target_id
        self.new_value = new_value
        self.mode = mode
        self.last_warning: str | None = None

    def mutate_safe(
        self,
        tree: Tree,
        node_id: str,
        new_value: str,
        mode: str = "ast",
    ) -> tuple[Tree, str | None]:
        """Safely mutates the target node in a copy of the parse tree.

        Returns (mutated_tree, None) on success, or (original_tree, warning_message) on failure.
        """
        try:
            mutated = self.mutate(tree, node_id, new_value, mode=mode)
            self.last_warning = None
            return mutated, None
        except ValueError as exc:
            self.last_warning = str(exc)
            return tree, str(exc)

    def mutate(
        self,
        tree: Tree,
        node_id: str,
        new_value: str,
        mode: str = "ast",
    ) -> Tree:
        """Mutates the target node in a copy of the tree. Raises ValueError on invalid mutations."""
        tree_copy = copy.deepcopy(tree)
        indexed = _index_tree_nodes(tree_copy, mode=mode)

        if node_id not in indexed:
            raise ValueError(f"Node ID '{node_id}' not found in parse tree")

        target_node, parent, child_index = indexed[node_id]

        if isinstance(target_node, Tree):
            data = target_node.data
            if data in ("add", "sub", "mul", "div", "eq", "ne"):
                op_key = new_value.strip().lower()
                if op_key not in VALID_OPERATORS:
                    raise ValueError(
                        f"Invalid operator '{new_value}'. Valid operators are: +, -, *, /, ==, !="
                    )
                target_node.data = VALID_OPERATORS[op_key]
            elif data == "number":
                val_str = new_value.strip()
                try:
                    float(val_str)
                except ValueError:
                    raise ValueError(f"Invalid numeric literal '{new_value}'") from None
                target_node.children = [Token("NUMBER", val_str)]
            elif data == "boolean":
                val_str = new_value.strip().lower()
                if val_str not in ("true", "false"):
                    raise ValueError(
                        f"Invalid boolean value '{new_value}'. Expected 'true' or 'false'"
                    )
                target_node.children = [Token("BOOLEAN", val_str)]
            elif data == "variable":
                ident = new_value.strip()
                if not ident.isidentifier() or ident in RESERVED_KEYWORDS:
                    raise ValueError(f"Invalid identifier name '{new_value}'")
                target_node.children = [Token("IDENTIFIER", ident)]
            elif data == "type_spec":
                type_name = new_value.lstrip(":").strip()
                if not type_name.isidentifier() or type_name in RESERVED_KEYWORDS:
                    raise ValueError(f"Invalid type specification '{new_value}'")
                target_node.children = [Token("IDENTIFIER", type_name)]
            elif data in (
                "start",
                "block",
                "var_decl",
                "assign_stmt",
                "print_stmt",
                "if_stmt",
            ):
                raise ValueError(f"Cannot mutate structural node '{data}' directly")
            else:
                raise ValueError(
                    f"Cannot mutate node '{data}' with value '{new_value}'"
                )
        elif isinstance(target_node, Token):
            if parent is None or child_index is None:
                raise ValueError("Cannot mutate root token without parent")
            if target_node.type in ("IDENTIFIER", "CNAME"):
                ident = new_value.strip()
                if not ident.isidentifier() or ident in RESERVED_KEYWORDS:
                    raise ValueError(f"Invalid identifier name '{new_value}'")
                parent.children[child_index] = Token(target_node.type, ident)
            elif target_node.type == "NUMBER":
                val_str = new_value.strip()
                try:
                    float(val_str)
                except ValueError:
                    raise ValueError(f"Invalid numeric literal '{new_value}'") from None
                parent.children[child_index] = Token("NUMBER", val_str)
            elif target_node.type == "BOOLEAN":
                val_str = new_value.strip().lower()
                if val_str not in ("true", "false"):
                    raise ValueError(
                        f"Invalid boolean value '{new_value}'. Expected 'true' or 'false'"
                    )
                parent.children[child_index] = Token("BOOLEAN", val_str)
            else:
                raise ValueError(
                    f"Cannot mutate token '{target_node}' of type '{target_node.type}'"
                )
        else:
            raise TypeError(f"Unknown node type '{type(target_node)}'")

        return tree_copy

    def transform(self, tree: Tree) -> Tree:
        if self.node_id is not None and self.new_value is not None:
            return self.mutate(tree, self.node_id, self.new_value, mode=self.mode)
        return copy.deepcopy(tree)

    def __default__(self, data: str, children: list[Any], meta: Any) -> Tree:
        return Tree(data, children, meta)

    def __default_token__(self, token: Token) -> Token:
        return token
