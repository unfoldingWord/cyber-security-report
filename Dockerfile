
# Build stage
FROM cgr.dev/chainguard/python:latest-dev AS builder

WORKDIR /build

# Create a virtual environment in the build directory
RUN python -m venv venv

# Copy and install dependencies
COPY pyproject.toml .
RUN ./venv/bin/pip install --no-cache-dir --upgrade pip && \
    ./venv/bin/pip install --no-cache-dir \
    anyio>=4.13.0 \
    claude-agent-sdk==0.2.87 \
    feedparser>=6.0.11 \
    httpx>=0.28.1 \
    jinja2>=3.1.4 \
    pydantic>=2.13.0 \
    pydantic-settings>=2.14.0 \
    python-dotenv>=1.2.0 \
    pyyaml>=6.0.2

# Runtime stage
FROM cgr.dev/chainguard/python:latest

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /build/venv /app/venv

# Copy application code
COPY src/ src/
COPY templates/ templates/
COPY main.py .
COPY config.yaml .

# Set environment variables
ENV PATH="/app/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

# Run the application
ENTRYPOINT ["/app/venv/bin/python", "main.py"]
