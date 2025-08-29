# =============================================================================
# Multi-stage build for dev-agents
# =============================================================================

# Directories to mount
# /code: mount your git repos here
# /data: for storage / cache and logs

# Build stage - Install dependencies and build the package
FROM python:3.11-slim AS builder

# Set build arguments
ARG PYTHONUNBUFFERED=1
ARG PYTHONDONTWRITEBYTECODE=1

# Set environment variables for build
ENV PYTHONUNBUFFERED=${PYTHONUNBUFFERED} \
    PYTHONDONTWRITEBYTECODE=${PYTHONDONTWRITEBYTECODE} \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app
RUN mkdir src

# Copy package configuration files first (for better caching)
COPY pyproject.toml ./
COPY README.md ./
COPY LICENSE ./

# Install the package and its dependencies
RUN pip install --upgrade pip setuptools wheel \
    && pip install -e .[prod]

# =============================================================================
# Runtime stage - Create minimal runtime image
# =============================================================================

FROM python:3.11-slim AS runtime

# Set runtime arguments
ARG PYTHONUNBUFFERED=1
ARG VERSION=0.9.0

# Set environment variables
ENV PYTHONUNBUFFERED=${PYTHONUNBUFFERED} \
    PYTHONPATH=/app/src \
    APP_ENV=production

# Install runtime dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -m -g appuser appuser

# Create app directory and set ownership
RUN mkdir -p /app && chown -R appuser:appuser /app
RUN mkdir -p /code && chown -R appuser:appuser /code
RUN mkdir -p /data && chown -R appuser:appuser /data

# Set working directory
WORKDIR /app

# Copy Python environment from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Copy application files
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser config/ ./config/
COPY --chown=appuser:appuser README.md LICENSE pyproject.toml ./

# Create logs directory structure
RUN mkdir -p logs data/logs data/storage \
    && chown -R appuser:appuser logs data

# Switch to non-root user
USER appuser

# Configure git for safe directory
RUN git config --global --add safe.directory /code

# Add version label
LABEL version="${VERSION}" \
      description="Dev Agents - AI-powered development team automation" \
      maintainer="dev@codeligence.com"

# Expose port for entrypoints with callbacks
# EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 CMD python -c "import sys; sys.exit(0)" || exit 1

ENV CORE_LOG_DIR=/data/logs
ENV CORE_STORAGE_FILE_DIR=/data/storage

# Default command - run the CLI chat entrypoint
CMD ["python", "-m", "entrypoints.cli_chat"]
