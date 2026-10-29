from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from py_ast.core.compiler import CompilerPipeline
from py_ast.core.schemas import (
    CompilerDiagnostic,
    MutateNodeRequest,
    MutateNodeResponse,
    ParseAnalysisResponse,
    ParseRequest,
)
from py_ast.core.unparser import ASTNodeMutator, CodeUnparser

app = FastAPI(title="py-ast Compiler Studio API")
compiler = CompilerPipeline()
unparser = CodeUnparser()
mutator = ASTNodeMutator()

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=FileResponse)
def serve_index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/compile", response_model=ParseAnalysisResponse)
def compile_code(req: ParseRequest) -> ParseAnalysisResponse:
    return compiler.compile(req.code, mode=req.mode)


@app.post("/api/mutate", response_model=MutateNodeResponse)
def mutate_node(req: MutateNodeRequest) -> MutateNodeResponse:
    # 1. Parse incoming source code
    tree, parse_diags = compiler.safe_parse(req.code)
    if tree is None:
        warning_msg = (
            f"Cannot mutate: code has syntax errors: "
            f"{parse_diags[0].message if parse_diags else 'Parse error'}"
        )
        diagnostics = list(parse_diags)
        diagnostics.append(
            CompilerDiagnostic(
                message=warning_msg,
                severity="warning",
                code="INVALID_MUTATION",
            )
        )
        return MutateNodeResponse(
            code=req.code,
            cytoscape_graph=[],
            generated_python="",
            symbol_table=None,
            diagnostics=diagnostics,
            warning=warning_msg,
            warnings=[warning_msg],
            success=False,
        )

    # 2. Apply mutation safely
    mutated_tree, warning = mutator.mutate_safe(
        tree, req.node_id, req.new_value, mode=req.mode
    )

    if warning is not None:
        orig_analysis = compiler.compile(req.code, mode=req.mode)
        diagnostics = list(orig_analysis.diagnostics)
        diagnostics.append(
            CompilerDiagnostic(
                message=warning,
                severity="warning",
                code="INVALID_MUTATION",
            )
        )
        return MutateNodeResponse(
            code=req.code,
            cytoscape_graph=orig_analysis.cytoscape_graph,
            generated_python=orig_analysis.generated_python,
            symbol_table=orig_analysis.symbol_table,
            diagnostics=diagnostics,
            warning=warning,
            warnings=[warning],
            success=False,
        )

    # 3. Regenerate source code via CodeUnparser
    try:
        new_source = unparser.regenerate_source(mutated_tree)
    except Exception as exc:  # noqa: BLE001
        warning_msg = f"Failed to regenerate source: {exc}"
        orig_analysis = compiler.compile(req.code, mode=req.mode)
        diagnostics = list(orig_analysis.diagnostics)
        diagnostics.append(
            CompilerDiagnostic(
                message=warning_msg,
                severity="warning",
                code="UNPARSE_ERROR",
            )
        )
        return MutateNodeResponse(
            code=req.code,
            cytoscape_graph=orig_analysis.cytoscape_graph,
            generated_python=orig_analysis.generated_python,
            symbol_table=orig_analysis.symbol_table,
            diagnostics=diagnostics,
            warning=warning_msg,
            warnings=[warning_msg],
            success=False,
        )

    # 4. Verify regenerated code parses cleanly
    verified_tree, verify_diags = compiler.safe_parse(new_source)
    if verified_tree is None or any(d.severity == "error" for d in verify_diags):
        warning_msg = (
            f"Structural mutation created invalid syntax: "
            f"{verify_diags[0].message if verify_diags else 'Syntax error'}"
        )
        orig_analysis = compiler.compile(req.code, mode=req.mode)
        diagnostics = list(orig_analysis.diagnostics)
        diagnostics.append(
            CompilerDiagnostic(
                message=warning_msg,
                severity="warning",
                code="INVALID_MUTATION",
            )
        )
        return MutateNodeResponse(
            code=req.code,
            cytoscape_graph=orig_analysis.cytoscape_graph,
            generated_python=orig_analysis.generated_python,
            symbol_table=orig_analysis.symbol_table,
            diagnostics=diagnostics,
            warning=warning_msg,
            warnings=[warning_msg],
            success=False,
        )

    # 5. Full compilation of updated source
    updated_analysis = compiler.compile(new_source, mode=req.mode)
    return MutateNodeResponse(
        code=new_source,
        cytoscape_graph=updated_analysis.cytoscape_graph,
        generated_python=updated_analysis.generated_python,
        symbol_table=updated_analysis.symbol_table,
        diagnostics=updated_analysis.diagnostics,
        warning=None,
        warnings=[],
        success=True,
    )
