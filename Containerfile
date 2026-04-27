FROM registry.access.redhat.com/ubi9/python-311:latest

USER 0
WORKDIR /opt/app

# Copy build context
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir ".[postgres]" && \
    chown -R 1001:0 /opt/app && \
    chmod -R g=u /opt/app

USER 1001

EXPOSE 8080

# Single-replica readiness; behind a Postgres-backed deployment, scale via replicas.
CMD ["uvicorn", "fipsagents_platform.app:app", "--host", "0.0.0.0", "--port", "8080"]
