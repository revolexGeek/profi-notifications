# syntax=docker/dockerfile:1

# ── Dependencies (production only) ───────────────────────────────────────────
FROM oven/bun:1.3-alpine AS deps
WORKDIR /app
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile --production

# ── Runtime ──────────────────────────────────────────────────────────────────
FROM oven/bun:1.3-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production
COPY --from=deps /app/node_modules ./node_modules
COPY package.json tsconfig.json ./
COPY src ./src

EXPOSE 3000
USER bun

# Liveness/readiness probe using Bun itself (no curl needed).
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD bun --eval "const p=process.env.HTTP_PORT||3000;fetch('http://127.0.0.1:'+p+'/ready').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["bun", "run", "src/main.ts"]
