# Standard Next.js production multi-stage build.
FROM node:20-slim AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
# npm ci requires a committed package-lock.json, which this project does
# not have (generating one correctly requires resolving the real
# dependency tree against npm's registry - not possible from the
# environment this was built in, which has no network access). npm
# install works with or without a lock file, resolving here instead,
# inside Render's build environment which does have real network access.
RUN npm install

FROM node:20-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# NEXT_PUBLIC_* variables are baked in at BUILD time (Next.js convention) -
# they end up in client-side JS bundles, so only ever put non-secret,
# genuinely public values here (an API base URL is fine; an API key is not).
ARG NEXT_PUBLIC_API_BASE_URL
ARG NEXT_PUBLIC_WS_URL
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL \
    NEXT_PUBLIC_WS_URL=$NEXT_PUBLIC_WS_URL
RUN npm run build

FROM node:20-slim AS runtime
RUN useradd --create-home --shell /bin/bash appuser
WORKDIR /app
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD node -e "require('http').get('http://localhost:3000', r => process.exit(r.statusCode < 500 ? 0 : 1)).on('error', () => process.exit(1))"

CMD ["npm", "start"]
