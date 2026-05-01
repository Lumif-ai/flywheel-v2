FROM python:3.12-slim-bookworm AS base

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install WeasyPrint system dependencies (Pango, Cairo, GDK-Pixbuf)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz-subset0 \
    libcairo2 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    default-jre-headless \
    && rm -rf /var/lib/apt/lists/*

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
