FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir mcp==2.3.0

WORKDIR /app

COPY workspace/HANDBOOK.md /app/HANDBOOK.md
COPY --chmod=755 ward /usr/local/bin/ward
