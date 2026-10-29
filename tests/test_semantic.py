from fastapi.testclient import TestClient

from py_ast.api.server import app
from py_ast.core.compiler import CompilerPipeline
from py_ast.core.schemas import SourceSpan
from py_ast.core.semantic import SemanticAnalyzer, SymbolScope


def test_token_extraction() -> None:
    pipeline = CompilerPipeline()
    code = "var count = 42 + 8; if (count == 50) { print(count); }"
    tokens = pipeline.extract_tokens(code)

    assert len(tokens) > 0
    token_types = [t.type for t in tokens]
    assert "VAR" in token_types
    assert "IDENTIFIER" in token_types
    assert "NUMBER" in token_types
    assert "PLUS" in token_types
    assert "EQ" in token_types or any(t.value == "==" for t in tokens)

    # Validate TokenDTO span and line metadata
    first_tok = tokens[0]
    assert first_tok.value == "var"
    assert first_tok.line == 1
    assert first_tok.column == 1
    assert isinstance(first_tok.span, SourceSpan)
    assert first_tok.span.start_line == 1
    assert first_tok.span.start_column == 1


def test_token_extraction_with_invalid_chars() -> None:
    pipeline = CompilerPipeline()
    # Should safely capture available tokens up to lexical fault without unhandled exception
    tokens = pipeline.extract_tokens("var x = 10 $#@")
    assert len(tokens) >= 4
    assert tokens[0].value == "var"
    assert tokens[1].value == "x"


def test_safe_parse_valid() -> None:
    pipeline = CompilerPipeline()
    code = "let x = 10; print(x);"
    tree, diagnostics = pipeline.safe_parse(code)

    assert tree is not None
    assert len(diagnostics) == 0


def test_safe_parse_syntax_error() -> None:
    pipeline = CompilerPipeline()
    # Missing expression after '='
    bad_code = "var x = ;"
    tree, diagnostics = pipeline.safe_parse(bad_code)

    assert tree is None
    assert len(diagnostics) == 1
    diag = diagnostics[0]
    assert diag.severity == "error"
    assert diag.line is not None
    assert diag.column is not None
    assert diag.code == "UNEXPECTED_TOKEN"


def test_safe_parse_invalid_character() -> None:
    pipeline = CompilerPipeline()
    bad_code = "@invalid"
    tree, diagnostics = pipeline.safe_parse(bad_code)

    assert tree is None
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "UNEXPECTED_CHARACTERS"
    assert diagnostics[0].line == 1


def test_symbol_scope_hierarchy() -> None:
    root = SymbolScope(name="global", level=0)
    root.define("global_var", symbol_type="int")

    child1 = root.create_child_scope(name="if_branch")
    child1.define("child_var", symbol_type="string")

    child2 = child1.create_child_scope(name="nested_block")
    child2.define("nested_var", symbol_type="bool")

    # Scope level verification
    assert root.level == 0
    assert child1.level == 1
    assert child2.level == 2

    # Resolution bubble up
    assert child2.resolve("nested_var") is not None
    assert child2.resolve("child_var") is not None
    assert child2.resolve("global_var") is not None
    assert root.resolve("child_var") is None

    # Current scope isolation
    assert child1.lookup_current("global_var") is None
    assert child1.lookup_current("child_var") is not None

    # Serialization to DTO
    dto = root.to_dto()
    assert dto.scope_name == "global"
    assert "global_var" in dto.symbols
    assert len(dto.children) == 1
    assert dto.children[0].scope_name == "if_branch"
    assert "child_var" in dto.children[0].symbols
    assert len(dto.children[0].children) == 1
    assert dto.children[0].children[0].scope_name == "nested_block"


def test_symbol_scope_shadowing() -> None:
    parent = SymbolScope(name="global", level=0)
    parent.define("x", symbol_type="int")

    child = parent.create_child_scope(name="block")
    child.define("x", symbol_type="float")

    resolved_parent = parent.resolve("x")
    resolved_child = child.resolve("x")

    assert resolved_parent is not None and resolved_parent.symbol_type == "int"
    assert resolved_child is not None and resolved_child.symbol_type == "float"


def test_semantic_variable_declarations() -> None:
    pipeline = CompilerPipeline()
    analyzer = SemanticAnalyzer()
    code = """
    var a = 10;
    let b: bool = true;
    var c;
    """
    tree, diags = pipeline.safe_parse(code)
    assert tree is not None
    assert len(diags) == 0

    table, sem_diags = analyzer.analyze(tree)
    assert len(sem_diags) == 0
    assert "a" in table.symbols
    assert "b" in table.symbols
    assert table.symbols["b"].symbol_type == "bool"
    assert "c" in table.symbols


def test_semantic_multi_level_if_else() -> None:
    pipeline = CompilerPipeline()
    analyzer = SemanticAnalyzer()
    code = """
    var a = 1;
    if (a == 1) {
        var b = 2;
        print(a);
        print(b);
    } else {
        var c = 3;
        print(c);
    }
    """
    tree, diags = pipeline.safe_parse(code)
    assert tree is not None
    assert len(diags) == 0

    table, sem_diags = analyzer.analyze(tree)
    assert len(sem_diags) == 0
    assert "a" in table.symbols
    assert len(table.children) == 2

    if_scope = table.children[0]
    assert if_scope.scope_name == "if_branch"
    assert if_scope.scope_level == 1
    assert "b" in if_scope.symbols

    else_scope = table.children[1]
    assert else_scope.scope_name == "else_branch"
    assert else_scope.scope_level == 1
    assert "c" in else_scope.symbols


def test_semantic_unresolved_identifier() -> None:
    pipeline = CompilerPipeline()
    analyzer = SemanticAnalyzer()
    code = "print(unknown_var);"

    tree, _ = pipeline.safe_parse(code)
    assert tree is not None

    _, sem_diags = analyzer.analyze(tree)
    assert len(sem_diags) == 1
    assert sem_diags[0].code == "UNRESOLVED_IDENTIFIER"
    assert "unknown_var" in sem_diags[0].message
    assert sem_diags[0].line == 1


def test_semantic_unresolved_out_of_scope() -> None:
    pipeline = CompilerPipeline()
    analyzer = SemanticAnalyzer()
    code = """
    if (true == true) {
        var local_val = 99;
    }
    print(local_val);
    """
    tree, _ = pipeline.safe_parse(code)
    assert tree is not None

    _, sem_diags = analyzer.analyze(tree)
    assert len(sem_diags) == 1
    assert sem_diags[0].code == "UNRESOLVED_IDENTIFIER"
    assert "local_val" in sem_diags[0].message


def test_semantic_duplicate_declaration() -> None:
    pipeline = CompilerPipeline()
    analyzer = SemanticAnalyzer()
    code = """
    var duplicate = 10;
    var duplicate = 20;
    """
    tree, _ = pipeline.safe_parse(code)
    assert tree is not None

    _, sem_diags = analyzer.analyze(tree)
    assert len(sem_diags) == 1
    assert sem_diags[0].code == "DUPLICATE_DECLARATION"
    assert "duplicate" in sem_diags[0].message


def test_pipeline_compile_success() -> None:
    pipeline = CompilerPipeline()
    code = """
    var x = 10;
    if (x == 10) {
        var y = 20;
        print(y);
    }
    """
    response = pipeline.compile(code)

    assert not response.has_errors
    assert len(response.diagnostics) == 0
    assert len(response.tokens) > 0
    assert "x = 10" in response.generated_python
    assert "if (x == 10):" in response.generated_python
    assert len(response.cytoscape_graph) > 0
    assert response.symbol_table is not None
    assert "x" in response.symbol_table.symbols
    assert len(response.symbol_table.children) == 1
    assert "y" in response.symbol_table.children[0].symbols


def test_pipeline_compile_error_boundary() -> None:
    pipeline = CompilerPipeline()
    response = pipeline.compile("invalid syntax == ;")

    assert response.has_errors
    assert len(response.diagnostics) > 0
    assert response.generated_python == ""
    assert response.symbol_table is None
    assert response.cytoscape_graph == []


def test_api_compile_endpoint() -> None:
    client = TestClient(app)

    # Valid payload
    valid_resp = client.post(
        "/api/compile", json={"code": "var num = 100; print(num);"}
    )
    assert valid_resp.status_code == 200
    data = valid_resp.json()
    assert "generated_python" in data
    assert "num = 100" in data["generated_python"]
    assert "symbol_table" in data
    assert "num" in data["symbol_table"]["symbols"]
    assert len(data["diagnostics"]) == 0

    # Payload with syntax error handled gracefully via error boundary
    error_resp = client.post("/api/compile", json={"code": "var broken = ;"})
    assert error_resp.status_code == 200
    err_data = error_resp.json()
    assert len(err_data["diagnostics"]) > 0
    assert err_data["diagnostics"][0]["severity"] == "error"


def test_semantic_assignment_statements() -> None:
    pipeline = CompilerPipeline()
    analyzer = SemanticAnalyzer()

    # Valid assignment to declared variable
    code_valid = "var declared = 10; declared = 20;"
    tree_valid, _ = pipeline.safe_parse(code_valid)
    assert tree_valid is not None
    _, diags_valid = analyzer.analyze(tree_valid)
    assert len(diags_valid) == 0

    # Unresolved assignment to undeclared variable
    code_invalid = "undeclared = 50;"
    tree_invalid, _ = pipeline.safe_parse(code_invalid)
    assert tree_invalid is not None
    _, diags_invalid = analyzer.analyze(tree_invalid)
    assert len(diags_invalid) == 1
    assert diags_invalid[0].code == "UNRESOLVED_IDENTIFIER"
    assert "undeclared" in diags_invalid[0].message


def test_symbol_table_and_scope_helpers() -> None:
    scope = SymbolScope(name="test_scope", level=0)
    scope.define("var_a", symbol_type="int")

    # Scope dict / membership helpers
    assert "var_a" in scope
    assert "missing" not in scope
    assert scope["var_a"].name == "var_a"
    try:
        _ = scope["nonexistent"]
        assert False, "Should have raised KeyError"
    except KeyError:
        pass

    # Table DTO helpers
    dto = scope.to_dto()
    assert "var_a" in dto
    assert "missing" not in dto
    assert dto["var_a"].name == "var_a"
    assert dto.get_symbol("var_a") is not None
    assert dto.get_symbol("nonexistent") is None


def test_standalone_block_scope() -> None:
    pipeline = CompilerPipeline()
    analyzer = SemanticAnalyzer()
    code = "{ var block_var = 123; print(block_var); }"
    tree, _ = pipeline.safe_parse(code)
    assert tree is not None

    table, diags = analyzer.analyze(tree)
    assert len(diags) == 0
    assert len(table.children) == 1
    assert table.children[0].scope_name == "block"
    assert "block_var" in table.children[0].symbols


def test_expressions_and_operators() -> None:
    pipeline = CompilerPipeline()
    code = """
    var diff = 20 - 5;
    var prod = 4 * 3;
    var quot = 10 / 2;
    if (diff != prod) {
        print(quot);
    }
    """
    res = pipeline.compile(code)
    assert not res.has_errors
    assert "(20 - 5)" in res.generated_python
    assert "(4 * 3)" in res.generated_python
    assert "(10 / 2)" in res.generated_python
    assert "!= " in res.generated_python


def test_cytoscape_none_node() -> None:
    pipeline = CompilerPipeline()
    assert pipeline.export_cytoscape_json(None) == []
