FROM python:3.12-slim

RUN pip install --no-cache-dir fastmcp==4.2.0

WORKDIR /app
COPY server.py collect.py /app/
RUN mkdir -p /evidence

EXPOSE 8000
CMD ["python", "/app/server.py"]
