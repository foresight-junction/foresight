FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir \
    fastmcp==4.2.0

COPY hospital/server.py /app/server.py
COPY hospital/collect.py /app/collect.py
COPY hospital/start.sh /app/start.sh
COPY hospital/ed72_sim/ /app/ed72_sim/
COPY hospital/config/default.json /app/config/default.json
ENV ED72_CONFIG=/app/config/default.json
COPY workspace/HANDBOOK.md /app/HANDBOOK.md

RUN mkdir -p /evidence

EXPOSE 8000
CMD ["/bin/sh", "/app/start.sh"]
