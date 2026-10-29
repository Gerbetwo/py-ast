.PHONY: dev desktop test lint format clean

dev:
	uv run python -m py_ast.main --web-only

desktop:
	uv run python -m py_ast.main

test:
	uv run pytest -v --cov=src

lint:
	uv run ruff check src tests
	uv run mypy src

format:
	uv run ruff format src tests

clean:
	rm -rf .pytest_cache .mypy_cache .coverage build dist *.egg-info
