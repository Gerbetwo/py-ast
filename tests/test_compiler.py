import time
from contextlib import suppress

from fastapi.testclient import TestClient
from lark import Token, Tree

from py_ast.api.server import app
from py_ast.core.compiler import CompilerPipeline


def test_compiler_pipeline() -> None:
    pipeline = CompilerPipeline()
    sample_code = "x = 10 + 5; print(x);"

    tree = pipeline.parse_to_tree(sample_code)
    assert tree is not None

    generated = pipeline.generate_python(tree)
    assert "x = (10 + 5)" in generated
    assert "print(x)" in generated

    graph = pipeline.export_cytoscape_json(tree)
    assert len(graph) > 0


def test_cytoscape_payload_structure_and_categories() -> None:
    pipeline = CompilerPipeline()
    sample_code = "var x = 10 + 5; if (x == 15) { print(x); }"

    tree = pipeline.parse_to_tree(sample_code)
    assert tree is not None

    graph = pipeline.export_cytoscape_json(tree)
    assert len(graph) > 0

    nodes = [item["data"] for item in graph if "source" not in item["data"]]
    edges = [item["data"] for item in graph if "source" in item["data"]]

    assert len(nodes) > 0
    assert len(edges) > 0

    valid_categories = {"control_flow", "expression", "identifier", "error"}
    seen_categories: set[str] = set()

    for node in nodes:
        assert "id" in node
        assert "label" in node
        assert isinstance(node["label"], str)

        assert "category" in node
        assert node["category"] in valid_categories
        seen_categories.add(node["category"])

        assert "span" in node
        span = node["span"]
        assert "line" in span
        assert "column" in span
        assert "end_line" in span
        assert "end_column" in span
        assert span["line"] >= 1
        assert span["column"] >= 1
        assert span["end_line"] >= span["line"]
        assert span["end_column"] >= span["column"]

    # Verify key categories are assigned correctly
    assert "control_flow" in seen_categories
    assert "expression" in seen_categories
    assert "identifier" in seen_categories

    labels = {n["label"]: n["category"] for n in nodes}
    assert labels.get("if_stmt") == "control_flow"
    assert labels.get("var_decl") == "control_flow"
    assert labels.get("add") == "expression"
    assert labels.get("eq") == "expression"
    assert labels.get("x") == "identifier"

    # Verify edge connectivity
    node_ids = {n["id"] for n in nodes}
    for edge in edges:
        assert edge["source"] in node_ids
        assert edge["target"] in node_ids


def test_cytoscape_error_category_and_diagnostics() -> None:
    pipeline = CompilerPipeline()

    # 1. Error tree node
    err_token = Token("ERROR", "malformed_token")
    err_tree = Tree("error_node", [err_token])
    graph = pipeline.export_cytoscape_json(err_tree)
    nodes = [el["data"] for el in graph if "source" not in el["data"]]
    assert any(n["category"] == "error" for n in nodes)

    # 2. Semantic error in compilation pipeline
    response = pipeline.compile("print(unresolved_symbol);")
    assert response.has_errors
    nodes = [
        el["data"] for el in response.cytoscape_graph if "source" not in el["data"]
    ]
    error_nodes = [n for n in nodes if n["category"] == "error"]
    assert len(error_nodes) > 0
    assert any("unresolved_symbol" in n["label"] for n in error_nodes)


def test_cytoscape_cst_vs_ast_mode() -> None:
    pipeline = CompilerPipeline()
    sample_code = "var count = 42;"

    tree = pipeline.parse_to_tree(sample_code)
    assert tree is not None

    cst_graph = pipeline.export_cytoscape_json(tree, mode="cst")
    ast_graph = pipeline.export_cytoscape_json(tree, mode="ast")

    cst_nodes = [el["data"] for el in cst_graph if "source" not in el["data"]]
    ast_nodes = [el["data"] for el in ast_graph if "source" not in el["data"]]

    # CST includes parse tree wrapper non-terminals like 'number' and token leaf '42'
    cst_labels = [n["label"] for n in cst_nodes]
    ast_labels = [n["label"] for n in ast_nodes]

    assert "number" in cst_labels
    assert "42" in cst_labels
    # In AST mode, the redundant wrapper is collapsed into leaf value
    assert "42" in ast_labels
    assert len(ast_nodes) < len(cst_nodes)

    # Test filter_ast boolean toggle flag
    ast_graph_flag = pipeline.export_cytoscape_json(tree, filter_ast=True)
    cst_graph_flag = pipeline.export_cytoscape_json(tree, filter_ast=False)
    assert len(ast_graph_flag) == len(ast_graph)
    assert len(cst_graph_flag) == len(cst_graph)


def test_cytoscape_source_span_precision() -> None:
    pipeline = CompilerPipeline()
    code = "let alpha = 999;"

    tree = pipeline.parse_to_tree(code)
    graph = pipeline.export_cytoscape_json(tree)
    nodes = [el["data"] for el in graph if "source" not in el["data"]]

    alpha_node = next(n for n in nodes if n["label"] == "alpha")
    assert alpha_node["category"] == "identifier"
    assert alpha_node["span"]["line"] == 1
    assert alpha_node["span"]["column"] == 5
    assert alpha_node["span"]["end_line"] == 1
    assert alpha_node["span"]["end_column"] == 10


def test_api_static_and_compile_mode() -> None:
    client = TestClient(app)

    # 1. Root GET / serves index.html
    root_resp = client.get("/")
    assert root_resp.status_code == 200
    assert "text/html" in root_resp.headers["content-type"]
    assert "py-ast" in root_resp.text
    assert "monaco-editor" in root_resp.text
    assert "cytoscape" in root_resp.text
    assert "Arithmetic Evaluator" in root_resp.text
    assert "Variable Binding" in root_resp.text
    assert "Conditional Logic" in root_resp.text
    assert "btn-toggle-mode" in root_resp.text
    assert "200" in root_resp.text

    # 2. Static asset mount serves index.html
    static_resp = client.get("/static/index.html")
    assert static_resp.status_code == 200
    assert "text/html" in static_resp.headers["content-type"]

    # 3. POST /api/compile with mode=ast
    ast_resp = client.post(
        "/api/compile", json={"code": "var val = 123;", "mode": "ast"}
    )
    assert ast_resp.status_code == 200
    ast_data = ast_resp.json()
    assert len(ast_data["cytoscape_graph"]) > 0

    # 4. POST /api/compile with mode=cst
    cst_resp = client.post(
        "/api/compile", json={"code": "var val = 123;", "mode": "cst"}
    )
    assert cst_resp.status_code == 200
    cst_data = cst_resp.json()
    assert len(cst_data["cytoscape_graph"]) > len(ast_data["cytoscape_graph"])


def test_ast_compute_performance_benchmark_500_loc() -> None:
    pipeline = CompilerPipeline()
    lines = [f"x{i} = {i};" for i in range(500)]
    code = "\n".join(lines)
    assert len(code.splitlines()) == 500

    # Temporarily pause test coverage tracing if active to measure pure compute latency
    cov = None
    with suppress(Exception):
        import coverage

        cov = coverage.Coverage.current()
        if cov is not None:
            cov.stop()

    try:
        start_time = time.perf_counter()
        tree = pipeline.parse_to_tree(code)
        graph = pipeline.export_cytoscape_json(tree)
        elapsed = time.perf_counter() - start_time
    finally:
        if cov is not None:
            cov.start()

    assert tree is not None
    assert len(graph) > 0
    # Adhere strictly to AGENTS.md performance targets: <50ms AST compute for scripts <500LOC
    assert elapsed < 0.050, (
        f"AST compute for 500 LOC took {elapsed * 1000:.2f}ms, exceeding 50ms target"
    )
