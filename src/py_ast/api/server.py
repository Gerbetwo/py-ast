from fastapi import FastAPI

from py_ast.core.compiler import CompilerPipeline
from py_ast.core.schemas import ParseAnalysisResponse, ParseRequest

app = FastAPI(title="py-ast Compiler Studio API")
compiler = CompilerPipeline()


@app.post("/api/compile", response_model=ParseAnalysisResponse)
def compile_code(req: ParseRequest) -> ParseAnalysisResponse:
    return compiler.compile(req.code)
