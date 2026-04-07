FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY server/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

# Copy all source files
COPY models.py /app/models.py
COPY tasks.py /app/tasks.py
COPY openenv.yaml /app/openenv.yaml
COPY server/ /app/server/

# Create __init__.py files
RUN touch /app/__init__.py /app/server/__init__.py

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

ENV PYTHONPATH=/app
ENV FINREG_TASK=easy_structuring

CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000"]
