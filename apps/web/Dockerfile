# ==================================================
# BASE
# ==================================================
FROM node:24-slim AS base

WORKDIR /app

ENV NEXT_TELEMETRY_DISABLED=1

# ==================================================
# DEPENDENCIES
# ==================================================
FROM base AS deps

COPY package.json package-lock.json ./

RUN npm ci

# ==================================================
# BUILD
# ==================================================
FROM base AS builder

COPY --from=deps /app/node_modules ./node_modules
COPY . .

RUN npm run build

# ==================================================
# PRODUCTION RUNTIME
# ==================================================
FROM base AS runner

ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN groupadd --system --gid 1001 nodejs \
    && useradd --system --uid 1001 --gid nodejs nextjs

COPY --from=builder --chown=nextjs:nodejs \
  /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs \
  /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

CMD ["node", "server.js"]
