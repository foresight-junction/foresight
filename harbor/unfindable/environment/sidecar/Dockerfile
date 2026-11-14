FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UF_SCENARIO=pilot \
    UF_SEED=42 \
    UF_PROFILE=v0.2 \
    UF_OBSERVE=0 \
    UF_LIVE_REVEAL=0

RUN pip install --no-cache-dir \
    fastapi==0.162.7 \
    "uvicorn[standard]==0.54.0" \
    fastmcp==2.14.7 \
    faker==40.54.0 \
    pydantic==2.14.3

WORKDIR /app
COPY app/ /app/app/
COPY scenarios/ /app/scenarios/
COPY collect.py start.sh /app/
RUN mkdir -p /evidence

EXPOSE 8000
CMD ["/bin/sh", "/app/start.sh"]
