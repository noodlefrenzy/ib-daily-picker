# Multi-stage build for IB Daily Picker Discord Bot
# Stage 1: Builder - installs dependencies and prepares the package
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements first for better caching
COPY pyproject.toml .
COPY src/ src/

# Install the package
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .


# Stage 2: Runtime - minimal image for running the bot
FROM python:3.12-slim AS runtime

WORKDIR /app

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY --chown=appuser:appuser src/ src/

# Create directories for data and strategies
RUN mkdir -p /home/appuser/.ib-picker/data /home/appuser/.ib-picker/strategies && \
    chown -R appuser:appuser /home/appuser/.ib-picker

# Copy example strategy files if they exist
COPY --chown=appuser:appuser strategies/ /home/appuser/.ib-picker/strategies/

# Switch to non-root user
USER appuser

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    IB_PICKER_CONFIG_DIR=/home/appuser/.ib-picker \
    IB_PICKER_STRATEGIES_DIR=/home/appuser/.ib-picker/strategies

# Health check - the bot should respond to the process being alive
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Run the Discord bot
CMD ["python", "-m", "ib_daily_picker", "bot", "run"]
