from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from py_ast.core.compiler import CompilerPipeline
from py_ast.core.schemas import ParseAnalysisResponse, ParseRequest

app = FastAPI(title="py-ast Compiler Studio API")
compiler = CompilerPipeline()

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=FileResponse)
def serve_index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/compile", response_model=ParseAnalysisResponse)
def compile_code(req: ParseRequest) -> ParseAnalysisResponse:
    return compiler.compile(req.code, mode=req.mode)
