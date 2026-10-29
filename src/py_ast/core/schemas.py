from typing import Any

from pydantic import BaseModel, Field


class SourceSpan(BaseModel):
    start_line: int
    start_column: int
    end_line: int | None = None
    end_column: int | None = None


class TokenDTO(BaseModel):
    type: str
    value: str
    line: int
    column: int
    span: SourceSpan


class CompilerDiagnostic(BaseModel):
    message: str
    severity: str = "error"
    line: int | None = None
    column: int | None = None
    span: SourceSpan | None = None
    code: str | None = None


class SymbolDTO(BaseModel):
    name: str
    symbol_type: str = "variable"
    scope_level: int = 0
    span: SourceSpan | None = None
    line: int | None = None
    column: int | None = None


class SymbolTableDTO(BaseModel):
    scope_name: str = "global"
    scope_level: int = 0
    parent_scope: str | None = None
    symbols: dict[str, SymbolDTO] = Field(default_factory=dict)
    children: list["SymbolTableDTO"] = Field(default_factory=list)

    def get_symbol(self, name: str) -> SymbolDTO | None:
        return self.symbols.get(name)

    def __contains__(self, name: object) -> bool:
        return name in self.symbols

    def __getitem__(self, name: str) -> SymbolDTO:
        return self.symbols[name]


class ParseRequest(BaseModel):
    code: str
    mode: str = "ast"


class ParseAnalysisResponse(BaseModel):
    tokens: list[TokenDTO] = Field(default_factory=list)
    generated_python: str = ""
    cytoscape_graph: list[dict[str, Any]] = Field(default_factory=list)
    symbol_table: SymbolTableDTO | None = None
    diagnostics: list[CompilerDiagnostic] = Field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(d.severity == "error" for d in self.diagnostics)


class MutateNodeRequest(BaseModel):
    node_id: str
    new_value: str
    code: str
    mode: str = "ast"


class MutateNodeResponse(BaseModel):
    code: str
    cytoscape_graph: list[dict[str, Any]] = Field(default_factory=list)
    generated_python: str = ""
    symbol_table: SymbolTableDTO | None = None
    diagnostics: list[CompilerDiagnostic] = Field(default_factory=list)
    warning: str | None = None
    warnings: list[str] = Field(default_factory=list)
    success: bool = True
