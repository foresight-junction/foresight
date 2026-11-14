FROM node:22-slim AS node

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir mcp==2.3.0

# Preinstall OpenCode so Harbor's agent setup skips its cold install (apt + nvm + npm takes
# about 7 minutes and overruns Harbor's 360 s setup limit). Harbor accepts any installed
# version when the run doesn't pin one, so a plain `harbor run -a opencode -m <model>` starts at once.
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && npm i -g opencode-ai@1.19.5 \
    && npm cache clean --force \
    && opencode --version

WORKDIR /app

COPY workspace/HANDBOOK.md /app/HANDBOOK.md
COPY --chmod=755 ward /usr/local/bin/ward
