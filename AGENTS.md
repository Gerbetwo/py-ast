```markdown
# AGENTS.md - Guidance & Architectural Standards for Coding Agents

## 1. Project Purpose & Scope
This repository provides a lightweight, educational compiler and AST visualization engine (`py-ast`). The application is designed for a single-user experience (e.g., classroom demonstrations, professors, and students) to visually inspect EBNF parsing, semantic analysis, code generation, and AST graph structures in real time.

### Core Philosophy
* **Agile Execution & High Velocity**: Build straightforward, working features rapidly.
* **Zero Technical Debt**: Keep code clean, typed, formatted, and fully covered by tests at every commit.
* **Radical Simplicity**: Implement raw, standard, standard-compliant Python code. Avoid speculative features, premature abstractions, or innovation for the sake of complexity.
* **Single-User Target**: Optimize for zero-friction local desktop usage (PyWebview) and single-container web deployment (FastAPI + Docker).

---

## 2. System Architecture & Tech Stack


```

+---------------------------------------------------------------------------------+
|                                 USER INTERFACE                                  |
|   Monaco Editor (Code Editor)  <-->  Cytoscape.js / Vis.js (AST Graph Viewer)   |
+---------------------------------------------------------------------------------+
^
| WebSocket / REST API
v
+---------------------------------------------------------------------------------+
|                            CORE PYTHON BACKEND ENGINE                           |
|                                                                                 |
|  +--------------------+   +--------------------+   +-------------------------+  |
|  |  1. Lexer/Parser   |   |  2. Semantic Anal. |   |   3. Code Generator     |  |
|  | (Lark / EBNF Rules)| -->| (Symbol Table/Type)| -->| (AST Visitor/Unparser)  |  |
|  +--------------------+   +--------------------+   +-------------------------+  |
+---------------------------------------------------------------------------------+
^
| Deployment Packaging
+--------------------+--------------------+
|                                         |
v                                         v
[ Desktop App Envelope ]                  [ Web Deployment ]
PyWebview + PyInstaller                    FastAPI + Docker

```

### Technology Summary
* **Language Runtime**: Python 3.11+ / 3.13 (managed strictly via `uv`).
* **Parser Engine**: `lark` (EBNF grammar parsing with LALR / Earley dynamic execution).
* **Graph & AST Analysis**: Built-in `ast`, `networkx`, and `graphviz` export utilities.
* **API & Frontend Framework**: `FastAPI` REST endpoints serving integrated Monaco Editor and Cytoscape.js graph payloads.
* **Desktop Packaging**: `pywebview` (local native window engine) + `pyinstaller`.
* **Web Packaging**: Docker + Uvicorn (`fastapi>=0.110.0`).

---

## 3. Strict Repository Layout


```

py-ast/
├── .antigravity/
│   └── skills/
│       └── verify-compiler.md   # Automated compiler pipeline checks
├── .github/
│   └── workflows/
│       └── ci.yml               # Automated CI (ruff, mypy, pytest)
├── src/
│   └── py_ast/
│       ├── api/
│       │   └── server.py        # Thin FastAPI HTTP route layer
│       ├── core/
│       │   └── compiler.py      # Lexer, EBNF grammar, Transformer, Graph Exporters
│       ├── **init**.py
│       ├── main.py              # Application entry point (Web/Desktop switch)
│       └── py.typed             # PEP 561 inline typing indicator
├── tests/
│   └── test_compiler.py         # End-to-end pipeline & component tests
├── Makefile                     # Developer interface for standard targets
├── pyproject.toml               # Project metadata & dependency declarations
└── uv.lock                      # Deterministic lockfile

```

---

## 4. Development & Quality Assurance Commands

Always use `uv` for execution. Execute these exact commands during development and before finalizing any pull request:

```bash
# 1. Start Web Server Mode
uv run python -m py_ast.main --web-only

# 2. Start Native Desktop Window Mode
uv run python -m py_ast.main

# 3. Format & Lint Codebase
uv run ruff check src tests --fix
uv run ruff format src tests

# 4. Type Verification
uv run mypy src

# 5. Execute Test Suite with Coverage
uv run pytest -v --cov=src

# 6. Make Helpers (Shortcuts)
make dev       # Start web server
make desktop   # Launch PyWebview desktop envelope
make lint      # Run ruff + mypy
make test      # Run pytest suite with coverage

```

---

## 5. Non-Negotiable Engineering Rules for Coding Agents

### Rule 1: Zero Technical Debt

* Never leave unused imports, dead functions, or commented-out logic in modified files.
* Every new core module or feature must include corresponding `pytest` unit tests in `tests/`.
* Code modified by agents must pass `ruff check`, `mypy`, and `pytest` cleanly before completion.

### Rule 2: Absolute Simplicity Over Abstraction

* Prefer concrete functions and simple classes over deeply nested inheritance or generic meta-programming.
* Do not add database connectors, multi-tenant auth frameworks, or complex state stores. The system is designed strictly for a single user/session.
* Keep route handlers in `src/py_ast/api/server.py` thin; delegate core transformations to `CompilerPipeline` in `src/py_ast/core/compiler.py`.

### Rule 3: Single-Source Data Flow

* Lexer/Parser output (`lark.Tree` / `lark.Token`) flows into semantic validation/transformation, which directly produces:
1. High-level Python generated code (unparsed string).
2. Cytoscape-compatible JSON graph elements (`[{"data": {"id": ..., "label": ...}}, ...]`).


* Do not duplicate parse tree traversals; keep graph extraction and code transformation clean and unified via standard AST visitors or Lark Transformers.

### Rule 4: Zero External Runtime Overhead

* Do not introduce heavy frontend or backend dependencies without explicit user request.
* All APIs must return light, JSON-serializable models using Pydantic `BaseModel`.

---

## 6. Compiler Component Guidelines

### EBNF Grammar & Lark Parser

* Grammars are defined clearly in string declarations or dedicated `.lark` files using Lark EBNF syntax.
* Keep terminal rules capitalized (e.g., `IDENTIFIER`, `NUMBER`, `WS`) and non-terminal rules lowercase (e.g., `assign_stmt`, `expr`).
* Dynamic LALR parsing is default for high performance; fall back to Earley execution only when handling complex ambiguous grammars.

### Cytoscape Graph Payload Format

The AST graph backend must always return Cytoscape.js compatible element arrays:

```json
[
  { "data": { "id": "0", "label": "start" } },
  { "data": { "id": "1", "label": "assign_stmt" } },
  { "data": { "source": "0", "target": "1" } }
]

```

---

## 7. Agent Verification Workflow

When completing any instruction or generating code, the AI agent must perform the following validation steps sequentially:

1. **Lint Check**: Run `uv run ruff check src tests` to ensure style conformance.
2. **Type Check**: Run `uv run mypy src` to verify static typing.
3. **Test Execution**: Run `uv run pytest` to guarantee all compiler unit tests pass without regressions.

```

```