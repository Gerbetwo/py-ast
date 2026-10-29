# py-ast | Educational Compiler & AST Visualizer Studio

[![CI Pipeline](https://github.com/Gerbetwo/py-ast/actions/workflows/ci.yml/badge.svg)](https://github.com/Gerbetwo/py-ast/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

`py-ast` is an educational compiler backend, sandboxed execution runtime, and interactive Abstract Syntax Tree (AST) visualizer studio. Designed for computer science students, professors, and compiler enthusiasts, it provides real-time visualization of EBNF parsing, lexical analysis, semantic scope analysis, AST node mutations, Python code generation, and sandboxed code execution.

---

## Key Features

- **Interactive Visual Studio**: Web workbench powered by Monaco Editor and Cytoscape.js for dynamic DAG graph renderings.
- **Dual Runtime Modes**: Run as a standalone native desktop app using `PyWebview` or as a web application via `FastAPI` & `Uvicorn`.
- **EBNF Grammar & Lark Parser**: Dynamic LALR dynamic execution parsing custom DSL constructs into structured ASTs or full CST parse trees.
- **Semantic Scope Analyzer**: Multi-level symbol table construction tracking scope hierarchy, symbol declarations, shadowing, and unresolved identifiers.
- **Sandboxed Execution Engine**: Process-isolated Python runtime with hard timeout bounds (capped at 2.0s) and strict builtin/module whitelisting for safe execution.
- **AST Node Mutation & Unparser**: Perform structural node edits directly on the AST and regenerate syntactically valid source code in real time.
- **Bidirectional Focus & Highlight**: Click AST nodes in Cytoscape to jump to exact Monaco editor line/column source spans, and vice versa.

---

## Architecture Overview

```
+---------------------------------------------------------------------------------+
|                                USER INTERFACE                                   |
|   Monaco Editor (Code Editor)  <-->  Cytoscape.js / Vis.js (AST Graph Viewer)   |
+---------------------------------------------------------------------------------+
                                         ^
                                         | WebSocket / REST API
                                         v
+---------------------------------------------------------------------------------+
|                           CORE PYTHON BACKEND ENGINE                            |
|                                                                                 |
|  +--------------------+   +--------------------+   +-------------------------+  |
|  |  1. Lexer/Parser   |   |  2. Semantic Anal. |   |   3. Code Generator     |  |
|  | (Lark / EBNF Rules)| -->| (Symbol Table/Type)| -->| (AST Visitor/Unparser)  |  |
|  +--------------------+   +--------------------+   +-------------------------+  |
+---------------------------------------------------------------------------------+
```

---

## Requirements

- **Python**: `>= 3.11` (or Python 3.13)
- **Package Manager**: [`uv`](https://github.com/astral-sh/uv) (recommended)
- **Docker** (optional, for container deployment)

---

## Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/Gerbetwo/py-ast.git
cd py-ast
```

### 2. Install Dependencies (Optional)

> **Note**: Running `python run.py` automatically checks for dependencies and installs or synchronizes them before launch.

If you prefer to install or synchronize dependencies manually:

- **Using `uv`** (recommended):
  ```bash
  uv sync --all-extras --dev
  ```
- **Using `pip`**:
  ```bash
  pip install -e .
  ```

### 3. Launch the Application

Use the cross-platform launcher `run.py` to run `py-ast` seamlessly across Windows, macOS, and Linux without requiring GNU Make. The script automatically detects `uv` (falling back to `pip`), syncs dependencies, and starts the application.

#### Option A: Native Desktop Window Mode (PyWebview)
```bash
python run.py
```
*Alternative (using `uv` directly or `make` on Linux/macOS):*
```bash
uv run python -m py_ast.main
# Or using the Makefile:
make desktop
```

#### Option B: Web Server Mode (FastAPI)
```bash
python run.py --web-only
```
*Alternative (using `uv` directly or `make` on Linux/macOS):*
```bash
uv run python -m py_ast.main --web-only
# Or using the Makefile:
make dev
```
Open your browser and navigate to `http://127.0.0.1:8000`.

Command-line arguments such as `--host` and `--port` are passed through seamlessly:
```bash
python run.py --web-only --host 0.0.0.0 --port 8080
```

---

## Docker Deployment

To build and run the production web server using Docker:

```bash
# Build Docker image
docker build -t py-ast .

# Run container on port 8000
docker run -p 8000:8000 py-ast
```

Or use the provided Makefile shortcuts:
```bash
make docker-build
make docker-run
```

---

## Development & Testing

This project maintains strict quality standards using `ruff`, `mypy`, and `pytest`.

```bash
# Run Linter & Formatter checks
uv run ruff check src tests
uv run mypy src

# Run Unit & Integration Test Suite with Coverage
uv run pytest -v --cov=src

# Shortcuts via Makefile
make lint
make format
make test
```

---

## API Reference

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/` | `GET` | Serves the main Visualizer Workbench UI (`index.html`) |
| `/api/compile` | `POST` | Parses code, extracts tokens, builds symbol table, and returns Cytoscape DAG graph |
| `/api/execute` | `POST` | Executes synthesized Python code inside a process-isolated sandbox |
| `/api/mutate` | `POST` | Mutates a specific AST node value/operator and regenerates updated source code |

---

## License

This project is open-source and licensed under the terms of the [MIT License](LICENSE).