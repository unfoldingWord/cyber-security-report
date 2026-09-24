
# Build stage
FROM cgr.dev/chainguard/python:latest-dev AS builder

WORKDIR /build

# Create a virtual environment in the build directory
RUN python -m venv venv

# Install the app and its dependencies straight from pyproject.toml, so the
# image never drifts from the declared dependency list. The project's `src`
# package is installed too but unused at runtime — the app runs from the copied
# `src/` in the workdir (see runtime stage).
COPY pyproject.toml .
COPY src/ src/
RUN ./venv/bin/pip install --no-cache-dir --upgrade pip && \
    ./venv/bin/pip install --no-cache-dir .

# Runtime stage
FROM cgr.dev/chainguard/python:latest

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /build/venv /app/venv

# Copy application code
COPY src/ src/
COPY templates/ templates/
COPY main.py .

# Set environment variables
ENV PATH="/app/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

# Run the application
ENTRYPOINT ["/app/venv/bin/python", "main.py"]
