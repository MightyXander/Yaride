# Yaride Mini App (TanStack Start + Nitro node-server).
FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# VITE_* подставляются на этапе сборки (задайте в Railway Variables сервиса miniapp).
ARG VITE_API_URL=
ARG VITE_YANDEX_MAPS_KEY=
ENV VITE_API_URL=$VITE_API_URL \
    VITE_YANDEX_MAPS_KEY=$VITE_YANDEX_MAPS_KEY

RUN npm run build

FROM node:22-alpine

WORKDIR /app

ENV NODE_ENV=production \
    HOST=0.0.0.0 \
    NITRO_HOST=0.0.0.0

COPY --from=build /app/.output ./.output
COPY --from=build /app/package.json ./package.json

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD wget -qO- "http://127.0.0.1:${PORT:-3000}/" > /dev/null || exit 1

CMD ["sh", "-c", "node .output/server/index.mjs"]
