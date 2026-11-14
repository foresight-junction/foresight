FROM node:22-alpine
RUN apk add --no-cache bash curl coreutils
WORKDIR /app
RUN npm install --no-audit --no-fund --global opencode-ai@1.19.5 \
    && opencode --version
