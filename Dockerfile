# syntax=docker/dockerfile:1
# Targets: dev (servidor Vite con recarga) · production (nginx + estáticos + proxy /api → backend)

FROM node:22-alpine AS base
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# ---- Desarrollo local: docker build --target dev ----
FROM base AS dev
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# ---- Compilación ----
FROM base AS build
# Por defecto la app llama a /api/v1 en su mismo origen (nginx lo reenvía al backend → sin CORS).
# Para apuntar directamente a otro origen: --build-arg VITE_API_BASE_URL=https://api.ejemplo.com/api/v1 (requiere CORS_ORIGINS en el backend).
ARG VITE_API_BASE_URL=/api/v1
ARG VITE_API_TIMEOUT_MS=30000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL VITE_API_TIMEOUT_MS=$VITE_API_TIMEOUT_MS
COPY . .
RUN npm run build

# ---- Producción ----
FROM nginx:1.27-alpine AS production
ENV BACKEND_URL=http://api:8000
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://localhost/ >/dev/null || exit 1
