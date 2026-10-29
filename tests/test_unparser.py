import time

import pytest
from fastapi.testclient import TestClient

from py_ast.api.server import app
from py_ast.core.compiler import CompilerPipeline
from py_ast.core.schemas import MutateNodeRequest, MutateNodeResponse
from py_ast.core.unparser import ASTNodeMutator, CodeUnparser


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def pipeline() -> CompilerPipeline:
    return CompilerPipeline()


@pytest.fixture
def unparser() -> CodeUnparser:
    return CodeUnparser()


@pytest.fixture
def mutator() -> ASTNodeMutator:
    return ASTNodeMutator()


# ----------------------------------------------------------------------
# 1. CodeUnparser Round-Trip & Code Regeneration Tests
# ----------------------------------------------------------------------


def test_unparser_variable_declarations(
    pipeline: CompilerPipeline, unparser: CodeUnparser
) -> None:
    cases = [
        "var x;",
        "var y: int;",
        "var z = 10;",
        "var w: float = 3.14;",
    ]
    for code in cases:
        tree = pipeline.parse_to_tree(code)
        regenerated = unparser.regenerate_source(tree)
        assert regenerated == code
        # Verify regenerated source re-parses cleanly
        reparsed = pipeline.parse_to_tree(regenerated)
        assert reparsed is not None


def test_unparser_arithmetic_precedence(
    pipeline: CompilerPipeline, unparser: CodeUnparser
) -> None:
    # Verify that precedence rules wrap parentheses only when syntactically required
    cases = [
        "x = 10 + 5;",
        "x = 10 + 5 * 2;",
        "x = (10 + 5) * 2;",
        "x = 10 - (5 + 2);",
        "x = 10 / (5 * 2);",
        "x = a == b;",
        "x = a != b + 2;",
    ]
    for code in cases:
        tree = pipeline.parse_to_tree(code)
        regenerated = unparser.regenerate_source(tree)
        assert regenerated == code
        reparsed = pipeline.parse_to_tree(regenerated)
        assert reparsed is not None


def test_unparser_control_flow_and_blocks(
    pipeline: CompilerPipeline, unparser: CodeUnparser
) -> None:
    code = "if (x == 15) {\n    x = 20;\n    print(x);\n} else {\n    x = 30;\n}"
    tree = pipeline.parse_to_tree(code)
    regenerated = unparser.regenerate_source(tree)
    assert regenerated == code
    reparsed = pipeline.parse_to_tree(regenerated)
    assert reparsed is not None


def test_unparser_none_and_empty(unparser: CodeUnparser) -> None:
    assert unparser.regenerate_source(None) == ""
    assert unparser.regenerate_python(None) == ""


# ----------------------------------------------------------------------
# 2. ASTNodeMutator Arithmetic & Operator Updates
# ----------------------------------------------------------------------


def test_mutate_number_literal(
    pipeline: CompilerPipeline, mutator: ASTNodeMutator, unparser: CodeUnparser
) -> None:
    code = "x = 10 + 5;"
    tree = pipeline.parse_to_tree(code)
    elements = pipeline.export_cytoscape_json(tree, mode="ast")

    # Find the node ID for "10"
    ten_node = next(
        e["data"]
        for e in elements
        if "source" not in e["data"] and e["data"]["label"] == "10"
    )

    mutated_tree = mutator.mutate(tree, ten_node["id"], "42")
    new_code = unparser.regenerate_source(mutated_tree)
    assert new_code == "x = 42 + 5;"

    # Verify reverse Python code synthesis accuracy
    py_code = pipeline.generate_python(mutated_tree)
    assert "x = (42 + 5)" in py_code
    assert unparser.regenerate_python(mutated_tree) == py_code


def test_mutate_binary_operators(
    pipeline: CompilerPipeline, mutator: ASTNodeMutator, unparser: CodeUnparser
) -> None:
    code = "x = 10 + 5;"
    tree = pipeline.parse_to_tree(code)
    elements = pipeline.export_cytoscape_json(tree, mode="ast")

    # Find the node ID for "add"
    add_node = next(
        e["data"]
        for e in elements
        if "source" not in e["data"] and e["data"]["label"] == "add"
    )

    # 1. Mutate + to - (using symbol)
    mutated_sub = mutator.mutate(tree, add_node["id"], "-")
    assert unparser.regenerate_source(mutated_sub) == "x = 10 - 5;"
    assert "x = (10 - 5)" in pipeline.generate_python(mutated_sub)

    # 2. Mutate + to * (using name "mul")
    mutated_mul = mutator.mutate(tree, add_node["id"], "mul")
    assert unparser.regenerate_source(mutated_mul) == "x = 10 * 5;"
    assert "x = (10 * 5)" in pipeline.generate_python(mutated_mul)

    # 3. Mutate + to / (using symbol)
    mutated_div = mutator.mutate(tree, add_node["id"], "/")
    assert unparser.regenerate_source(mutated_div) == "x = 10 / 5;"
    assert "x = (10 / 5)" in pipeline.generate_python(mutated_div)


def test_mutate_comparison_operators(
    pipeline: CompilerPipeline, mutator: ASTNodeMutator, unparser: CodeUnparser
) -> None:
    code = "if (x == 10) { print(x); }"
    tree = pipeline.parse_to_tree(code)
    elements = pipeline.export_cytoscape_json(tree, mode="ast")

    eq_node = next(
        e["data"]
        for e in elements
        if "source" not in e["data"] and e["data"]["label"] == "eq"
    )

    # Mutate == to !=
    mutated = mutator.mutate(tree, eq_node["id"], "!=")
    new_code = unparser.regenerate_source(mutated)
    assert "if (x != 10)" in new_code
    py_code = pipeline.generate_python(mutated)
    assert "if (x != 10):" in py_code


# ----------------------------------------------------------------------
# 3. ASTNodeMutator Identifier Renames & Variable Updates
# ----------------------------------------------------------------------


def test_mutate_identifier_assignment_target(
    pipeline: CompilerPipeline, mutator: ASTNodeMutator, unparser: CodeUnparser
) -> None:
    code = "x = 10 + 5;"
    tree = pipeline.parse_to_tree(code)
    elements = pipeline.export_cytoscape_json(tree, mode="ast")

    x_node = next(
        e["data"]
        for e in elements
        if "source" not in e["data"] and e["data"]["label"] == "x"
    )

    mutated_tree = mutator.mutate(tree, x_node["id"], "result_total")
    new_code = unparser.regenerate_source(mutated_tree)
    assert new_code == "result_total = 10 + 5;"

    py_code = pipeline.generate_python(mutated_tree)
    assert "result_total = (10 + 5)" in py_code


def test_mutate_identifier_in_var_decl(
    pipeline: CompilerPipeline, mutator: ASTNodeMutator, unparser: CodeUnparser
) -> None:
    code = "var count: int = 100;"
    tree = pipeline.parse_to_tree(code)
    elements = pipeline.export_cytoscape_json(tree, mode="ast")

    count_node = next(
        e["data"]
        for e in elements
        if "source" not in e["data"] and e["data"]["label"] == "count"
    )

    mutated_tree = mutator.mutate(tree, count_node["id"], "item_counter")
    new_code = unparser.regenerate_source(mutated_tree)
    assert new_code == "var item_counter: int = 100;"

    py_code = pipeline.generate_python(mutated_tree)
    assert "item_counter = 100" in py_code


def test_mutate_type_spec(
    pipeline: CompilerPipeline, mutator: ASTNodeMutator, unparser: CodeUnparser
) -> None:
    code = "var count: int = 100;"
    tree = pipeline.parse_to_tree(code)
    elements = pipeline.export_cytoscape_json(tree, mode="ast")

    type_node = next(
        e["data"]
        for e in elements
        if "source" not in e["data"] and e["data"]["label"] == ": int"
    )

    mutated_tree = mutator.mutate(tree, type_node["id"], "float")
    new_code = unparser.regenerate_source(mutated_tree)
    assert new_code == "var count: float = 100;"


def test_mutate_variable_in_print(
    pipeline: CompilerPipeline, mutator: ASTNodeMutator, unparser: CodeUnparser
) -> None:
    code = "x = 10; print(x);"
    tree = pipeline.parse_to_tree(code)
    elements = pipeline.export_cytoscape_json(tree, mode="ast")

    nodes = [e["data"] for e in elements if "source" not in e["data"]]
    # The second "x" is inside print_stmt
    print_var_node = [n for n in nodes if n["label"] == "x"][1]

    mutated_tree = mutator.mutate(tree, print_var_node["id"], "y")
    new_code = unparser.regenerate_source(mutated_tree)
    assert new_code == "x = 10;\nprint(y);"

    py_code = pipeline.generate_python(mutated_tree)
    assert "print(y)" in py_code


# ----------------------------------------------------------------------
# 4. ASTNodeMutator Invalid Mutation Handling
# ----------------------------------------------------------------------


def test_mutate_invalid_numeric_literal(
    pipeline: CompilerPipeline, mutator: ASTNodeMutator
) -> None:
    code = "x = 10 + 5;"
    tree = pipeline.parse_to_tree(code)
    elements = pipeline.export_cytoscape_json(tree, mode="ast")
    ten_node = next(
        e["data"]
        for e in elements
        if "source" not in e["data"] and e["data"]["label"] == "10"
    )

    with pytest.raises(ValueError, match="Invalid numeric literal"):
        mutator.mutate(tree, ten_node["id"], "not_a_number")

    # Safe mutate returns warning and retains original tree
    safe_tree, warning = mutator.mutate_safe(tree, ten_node["id"], "not_a_number")
    assert warning is not None
    assert "Invalid numeric literal" in warning
    assert safe_tree == tree


def test_mutate_invalid_identifier_name(
    pipeline: CompilerPipeline, mutator: ASTNodeMutator
) -> None:
    code = "x = 10 + 5;"
    tree = pipeline.parse_to_tree(code)
    elements = pipeline.export_cytoscape_json(tree, mode="ast")
    x_node = next(
        e["data"]
        for e in elements
        if "source" not in e["data"] and e["data"]["label"] == "x"
    )

    with pytest.raises(ValueError, match="Invalid identifier name"):
        mutator.mutate(tree, x_node["id"], "123invalid")

    with pytest.raises(ValueError, match="Invalid identifier name"):
        mutator.mutate(tree, x_node["id"], "var")  # Reserved keyword


def test_mutate_invalid_operator(
    pipeline: CompilerPipeline, mutator: ASTNodeMutator
) -> None:
    code = "x = 10 + 5;"
    tree = pipeline.parse_to_tree(code)
    elements = pipeline.export_cytoscape_json(tree, mode="ast")
    add_node = next(
        e["data"]
        for e in elements
        if "source" not in e["data"] and e["data"]["label"] == "add"
    )

    with pytest.raises(ValueError, match="Invalid operator"):
        mutator.mutate(tree, add_node["id"], "%")


def test_mutate_structural_node_error(
    pipeline: CompilerPipeline, mutator: ASTNodeMutator
) -> None:
    code = "x = 10 + 5;"
    tree = pipeline.parse_to_tree(code)
    elements = pipeline.export_cytoscape_json(tree, mode="ast")
    assign_node = next(
        e["data"]
        for e in elements
        if "source" not in e["data"] and e["data"]["label"] == "assign_stmt"
    )

    with pytest.raises(ValueError, match="Cannot mutate structural node"):
        mutator.mutate(tree, assign_node["id"], "invalid_structural_edit")


def test_mutate_nonexistent_node_id(
    pipeline: CompilerPipeline, mutator: ASTNodeMutator
) -> None:
    code = "x = 10 + 5;"
    tree = pipeline.parse_to_tree(code)
    with pytest.raises(ValueError, match="Node ID '9999' not found"):
        mutator.mutate(tree, "9999", "42")


def test_mutator_as_transformer_instance(
    pipeline: CompilerPipeline, unparser: CodeUnparser
) -> None:
    code = "x = 10 + 5;"
    tree = pipeline.parse_to_tree(code)
    elements = pipeline.export_cytoscape_json(tree, mode="ast")
    ten_node = next(
        e["data"]
        for e in elements
        if "source" not in e["data"] and e["data"]["label"] == "10"
    )

    # Initialize mutator with target_id / new_value and call .transform()
    mutator = ASTNodeMutator(node_id=ten_node["id"], new_value="99")
    mutated = mutator.transform(tree)
    assert unparser.regenerate_source(mutated) == "x = 99 + 5;"


# ----------------------------------------------------------------------
# 5. API Endpoint POST /api/mutate Tests
# ----------------------------------------------------------------------


def test_api_mutate_successful_arithmetic(client: TestClient) -> None:
    start_time = time.perf_counter()
    req = MutateNodeRequest(
        node_id="3",  # "10" in AST for "x = 10 + 5;"
        new_value="77",
        code="x = 10 + 5;",
    )
    response = client.post("/api/mutate", json=req.model_dump())
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    assert response.status_code == 200
    data = response.json()
    model = MutateNodeResponse.model_validate(data)

    assert model.success is True
    assert model.code == "x = 77 + 5;"
    assert "x = (77 + 5)" in model.generated_python
    assert len(model.cytoscape_graph) > 0
    assert model.warning is None

    # Verify requirement: within 150ms
    assert elapsed_ms < 150.0, f"Mutation took {elapsed_ms:.2f}ms, exceeding 150ms"


def test_api_mutate_successful_operator(client: TestClient) -> None:
    req = MutateNodeRequest(
        node_id="2",  # "add" in AST for "x = 10 + 5;"
        new_value="-",
        code="x = 10 + 5;",
    )
    response = client.post("/api/mutate", json=req.model_dump())
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["code"] == "x = 10 - 5;"
    assert "x = (10 - 5)" in data["generated_python"]


def test_api_mutate_successful_identifier(client: TestClient) -> None:
    req = MutateNodeRequest(
        node_id="1",  # "x" in AST for "x = 10 + 5;"
        new_value="new_var",
        code="x = 10 + 5;",
    )
    response = client.post("/api/mutate", json=req.model_dump())
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["code"] == "new_var = 10 + 5;"
    assert "new_var = (10 + 5)" in data["generated_python"]


def test_api_mutate_invalid_numeric_returns_warning_retaining_state(
    client: TestClient,
) -> None:
    initial_code = "x = 10 + 5;"
    req = MutateNodeRequest(
        node_id="3",
        new_value="invalid_num",
        code=initial_code,
    )
    response = client.post("/api/mutate", json=req.model_dump())
    assert response.status_code == 200
    data = response.json()

    assert data["success"] is False
    # Retains last valid state
    assert data["code"] == initial_code
    assert len(data["cytoscape_graph"]) > 0
    # Clear warning returned
    assert data["warning"] is not None
    assert "Invalid numeric literal" in data["warning"]
    assert any(
        d["severity"] == "warning" and "Invalid numeric literal" in d["message"]
        for d in data["diagnostics"]
    )


def test_api_mutate_invalid_operator_returns_warning(client: TestClient) -> None:
    initial_code = "x = 10 + 5;"
    req = MutateNodeRequest(
        node_id="2",
        new_value="%",
        code=initial_code,
    )
    response = client.post("/api/mutate", json=req.model_dump())
    assert response.status_code == 200
    data = response.json()

    assert data["success"] is False
    assert data["code"] == initial_code
    assert data["warning"] is not None
    assert "Invalid operator" in data["warning"]


def test_api_mutate_structural_node_returns_warning(client: TestClient) -> None:
    initial_code = "x = 10 + 5;"
    req = MutateNodeRequest(
        node_id="0",  # assign_stmt
        new_value="foo",
        code=initial_code,
    )
    response = client.post("/api/mutate", json=req.model_dump())
    assert response.status_code == 200
    data = response.json()

    assert data["success"] is False
    assert data["code"] == initial_code
    assert data["warning"] is not None
    assert "Cannot mutate structural node" in data["warning"]


def test_api_mutate_syntax_error_code(client: TestClient) -> None:
    req = MutateNodeRequest(
        node_id="1",
        new_value="y",
        code="x = = 10;",
    )
    response = client.post("/api/mutate", json=req.model_dump())
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["warning"] is not None
    assert "syntax errors" in data["warning"]


def test_mutate_boolean_literal(
    pipeline: CompilerPipeline, mutator: ASTNodeMutator, unparser: CodeUnparser
) -> None:
    code = "var flag = true;"
    tree = pipeline.parse_to_tree(code)
    elements = pipeline.export_cytoscape_json(tree, mode="ast")
    bool_node = next(
        e["data"]
        for e in elements
        if "source" not in e["data"] and e["data"]["label"] == "true"
    )

    mutated = mutator.mutate(tree, bool_node["id"], "false")
    assert unparser.regenerate_source(mutated) == "var flag = false;"

    with pytest.raises(ValueError, match="Invalid boolean value"):
        mutator.mutate(tree, bool_node["id"], "maybe")


def test_mutate_invalid_type_spec(
    pipeline: CompilerPipeline, mutator: ASTNodeMutator
) -> None:
    code = "var count: int = 100;"
    tree = pipeline.parse_to_tree(code)
    elements = pipeline.export_cytoscape_json(tree, mode="ast")
    type_node = next(
        e["data"]
        for e in elements
        if "source" not in e["data"] and e["data"]["label"] == ": int"
    )

    with pytest.raises(ValueError, match="Invalid type specification"):
        mutator.mutate(tree, type_node["id"], "123invalid")


def test_mutate_cst_mode(
    pipeline: CompilerPipeline, mutator: ASTNodeMutator, unparser: CodeUnparser
) -> None:
    code = "x = 10 + 5;"
    tree = pipeline.parse_to_tree(code)
    cst_elements = pipeline.export_cytoscape_json(tree, mode="cst")
    # In CST mode, token 10 is a child node
    token_10 = next(
        e["data"]
        for e in cst_elements
        if "source" not in e["data"] and e["data"]["label"] == "10"
    )

    mutated = mutator.mutate(tree, token_10["id"], "99", mode="cst")
    assert unparser.regenerate_source(mutated) == "x = 99 + 5;"


def test_mutator_identity_transform(pipeline: CompilerPipeline) -> None:
    code = "x = 10 + 5;"
    tree = pipeline.parse_to_tree(code)
    empty_mutator = ASTNodeMutator()
    transformed = empty_mutator.transform(tree)
    assert transformed == tree


def test_unparser_standalone_blocks_and_empty(
    pipeline: CompilerPipeline, unparser: CodeUnparser
) -> None:
    code = "{\n    x = 1;\n    y = 2;\n}"
    tree = pipeline.parse_to_tree(code)
    regenerated = unparser.regenerate_source(tree)
    assert regenerated == code


def test_api_mutate_unparse_error_fallback(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import py_ast.api.server as server_mod

    def broken_regenerate(tree):
        raise RuntimeError("Synthetic unparser explosion")

    monkeypatch.setattr(server_mod.unparser, "regenerate_source", broken_regenerate)

    req = MutateNodeRequest(node_id="3", new_value="42", code="x = 10 + 5;")
    response = client.post("/api/mutate", json=req.model_dump())
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "Synthetic unparser explosion" in data["warning"]
    assert data["code"] == "x = 10 + 5;"


def test_api_mutate_regenerated_syntax_error_fallback(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import py_ast.api.server as server_mod

    def broken_regenerate(tree):
        return "x = = 10;"

    monkeypatch.setattr(server_mod.unparser, "regenerate_source", broken_regenerate)

    req = MutateNodeRequest(node_id="3", new_value="42", code="x = 10 + 5;")
    response = client.post("/api/mutate", json=req.model_dump())
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "Structural mutation created invalid syntax" in data["warning"]
    assert data["code"] == "x = 10 + 5;"
