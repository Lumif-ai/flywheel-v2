FROM python:3.12-slim AS base

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies first (cache layer)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# Copy source code
COPY src/ ./src/

# Copy alembic for pre-deploy migrations
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Install the project itself
RUN uv sync --frozen

# Railway injects PORT env var; default to 8000 for local dev
CMD ["sh", "-c", "uv run uvicorn flywheel.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
