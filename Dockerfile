FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY server/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

# Copy all source files into /app
COPY models.py /app/models.py
COPY tasks.py /app/tasks.py
COPY openenv.yaml /app/openenv.yaml
COPY server/ /app/server/

# Ensure Python packages are importable from /app
RUN touch /app/__init__.py /app/server/__init__.py

# HuggingFace Spaces requires port 7860
EXPOSE 7860

# Health check on port 7860
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=5 \
    CMD curl -f http://localhost:7860/health || exit 1

ENV PYTHONPATH=/app
ENV FINREG_TASK=easy_structuring

# Run on port 7860 — required by HuggingFace Spaces
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "7860", "--timeout-keep-alive", "75"]
