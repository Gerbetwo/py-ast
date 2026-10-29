from py_ast.core.compiler import CompilerPipeline


def test_compiler_pipeline():
    pipeline = CompilerPipeline()
    sample_code = "x = 10 + 5; print(x);"

    tree = pipeline.parse_to_tree(sample_code)
    assert tree is not None

    generated = pipeline.generate_python(tree)
    assert "x = (10 + 5)" in generated
    assert "print(x)" in generated

    graph = pipeline.export_cytoscape_json(tree)
    assert len(graph) > 0
