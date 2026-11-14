FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir \
    fastmcp==4.2.0

COPY server.py collect.py start.sh /app/
COPY ed72_sim/ /app/ed72_sim/

RUN mkdir -p /evidence

EXPOSE 8000
CMD ["/bin/sh", "/app/start.sh"]
