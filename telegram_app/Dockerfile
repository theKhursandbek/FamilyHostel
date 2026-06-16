# ==============================================================================
# Telegram Mini App — multi-stage Docker build
#
# Stage 1: Build the Vite React app
# Stage 2: Copy dist/ into a minimal container for nginx to mount
# ==============================================================================

# ── Build stage ──────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies first (better layer caching)
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts

# Copy source and build
COPY . .

# Accept API URL as build arg so it's baked into the static bundle
ARG VITE_API_URL=https://your-backend-domain/api/v1

ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

# ── Production stage ─────────────────────────────────────────────────────────
# Minimal image that just holds the built files.
# Nginx reads them via a shared Docker volume.
FROM alpine:3.20 AS production

COPY --from=builder /app/dist /usr/share/nginx/html

# This container doesn't run a server — it only provides static files
# to the nginx container via a shared volume. Use a no-op entrypoint.
CMD ["echo", "telegram-app build complete — static files in /usr/share/nginx/html"]
