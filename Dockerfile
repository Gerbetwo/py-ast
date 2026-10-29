# Stage 1: Builder
FROM python:3.13-slim AS builder

# Copy uv binary from official astral image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Copy dependency specifications first for layer caching
COPY pyproject.toml uv.lock ./

# Install external dependencies without installing root project
RUN uv sync --frozen --no-dev --no-install-project

# Copy source code and perform frozen sync
COPY src ./src
RUN uv sync --frozen --no-dev

# Stage 2: Runner
FROM python:3.13-slim AS runner

WORKDIR /app

# Configure execution environment
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/src" \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000

# Copy virtual environment and source code
COPY --from=builder /app/.venv /app/.venv
COPY src ./src

# Expose FastAPI HTTP port
EXPOSE 8000

# Default command: launch web server mode
CMD ["python", "-m", "py_ast.main", "--web-only"]
