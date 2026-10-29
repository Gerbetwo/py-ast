# Antigravity AI Agent Rules & Architecture Context

## Project Overview
`py-ast` is a dual-target (Web + Desktop) compiler design laboratory and visual AST generator written in Python.

## Core Stack & Tooling
- **Language**: Python 3.11+
- **Package Manager**: `uv`
- **Compiler Front-End**: `Lark` (EBNF parsing, LALR/Earley execution)
- **Web Backend**: `FastAPI` + `Uvicorn`
- **Desktop Shell**: `PyWebview` (Native window rendering FastAPI app)
- **Linter & Formatter**: `ruff`
- **Type Checker**: `mypy`
- **Testing**: `pytest`

## Command Standards for AI Agents
Always execute commands using `uv run`:
- Run tests: `uv run pytest`
- Run test coverage: `uv run pytest --cov=src`
- Lint code: `uv run ruff check src tests`
- Format code: `uv run ruff format src tests`
- Type check: `uv run mypy src`
- Start dev server: `uv run python -m py_ast.app`

## Code Style & Rules
- Use strict type annotations on all function signatures.
- Keep the parsing and AST transformation logic decoupled from FastAPI routes.
- Modularize AST transformations into standard NodeVisitors/Transformers.
