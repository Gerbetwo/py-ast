from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from py_ast.core.compiler import CompilerPipeline

app = FastAPI(title="py-ast Compiler Studio API")
compiler = CompilerPipeline()


class ParseRequest(BaseModel):
    code: str


class ParseResponse(BaseModel):
    generated_python: str
    cytoscape_graph: list


@app.post("/api/compile", response_model=ParseResponse)
def compile_code(req: ParseRequest):
    try:
        tree = compiler.parse_to_tree(req.code)
        python_code = compiler.generate_python(tree)
        graph = compiler.export_cytoscape_json(tree)
        return ParseResponse(generated_python=python_code, cytoscape_graph=graph)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
