
# Build stage
FROM cgr.dev/chainguard/python:latest-dev AS builder

# uv installs dependencies straight from the lockfile — no project wheel build,
# so no build backend is needed and the image never drifts from pyproject.toml.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /build

# Use the image's Python; don't let uv fetch a managed interpreter.
ENV UV_PYTHON_DOWNLOADS=0 \
    UV_PROJECT_ENVIRONMENT=/build/.venv

# Install locked dependencies only (skip building/installing the project itself).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Runtime stage
FROM cgr.dev/chainguard/python:latest

WORKDIR /app

# Copy the dependency virtual environment from the builder
COPY --from=builder /build/.venv /app/.venv

# Copy application code (imported as the local `src` package from the workdir)
COPY src/ src/
COPY templates/ templates/
COPY main.py .

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

# Run the application
ENTRYPOINT ["/app/.venv/bin/python", "main.py"]
