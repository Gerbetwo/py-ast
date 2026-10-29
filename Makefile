.PHONY: dev desktop test lint format clean docker-build docker-run

dev:
	uv run python -m py_ast.main --web-only

desktop:
	uv run python -m py_ast.main

test:
	uv run pytest -v --cov=src

lint:
	uv run ruff check src tests && uv run mypy src

format:
	uv run ruff format src tests

docker-build:
	docker build -t py-ast .

docker-run:
	docker run -p 8000:8000 py-ast

clean:
	rm -rf .pytest_cache .mypy_cache .coverage build dist *.egg-info
