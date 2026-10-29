from typing import Any

from lark import Lark, Transformer

EBNF_GRAMMAR = """
    ?start: statement+

    ?statement: assign_stmt
             | print_stmt

    assign_stmt: IDENTIFIER "=" expr ";"
    print_stmt: "print" "(" expr ")" ";"

    ?expr: term
        | expr "+" term -> add
        | expr "-" term -> sub

    ?term: atom
        | term "*" atom -> mul
        | term "/" atom -> div

    ?atom: NUMBER       -> number
        | IDENTIFIER   -> variable
        | "(" expr ")"

    %import common.CNAME -> IDENTIFIER
    %import common.NUMBER
    %import common.WS
    %ignore WS
"""


class ASTToPythonTransformer(Transformer):
    def number(self, args: list[Any]) -> str:
        return str(args[0].value)

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

    def assign_stmt(self, args: list[Any]) -> str:
        return f"{args[0].value} = {args[1]}"

    def print_stmt(self, args: list[Any]) -> str:
        return f"print({args[0]})"

    def start(self, args: list[Any]) -> str:
        return "\n".join(args)


class CompilerPipeline:
    def __init__(self, grammar: str = EBNF_GRAMMAR) -> None:
        self.parser = Lark(grammar, parser="lalr")
        self.transformer = ASTToPythonTransformer()

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
