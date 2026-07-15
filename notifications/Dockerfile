FROM oven/bun:1.3.14-alpine AS deps
WORKDIR /app
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile --production

FROM oven/bun:1.3.14-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production

RUN apk add --no-cache tini=0.19.0-r3

COPY --chown=bun:bun --from=deps /app/node_modules ./node_modules
COPY --chown=bun:bun package.json tsconfig.json ./
COPY --chown=bun:bun src ./src

EXPOSE 3000
USER bun

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD bun --eval "const p=process.env.HTTP_PORT||3000;fetch('http://127.0.0.1:'+p+'/ready').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

ENTRYPOINT ["/sbin/tini", "--"]
CMD ["bun", "run", "src/main.ts"]
