---
name: verify-compiler
description: Run full compiler pipeline checks including parsing, AST generation, linting, and unit tests.
---

1. Run `uv run ruff check src tests` to ensure code style compliance.
2. Run `uv run mypy src` to verify static typing.
3. Run `uv run pytest` to execute all unit tests for Lexer, Parser, and Code Generator.
