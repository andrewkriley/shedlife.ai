FROM node:24-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir uv
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
COPY backend/src ./src
RUN uv sync --frozen --no-dev
COPY backend/alembic.ini ./alembic.ini
COPY backend/alembic ./alembic
COPY --from=frontend /frontend/dist /app/frontend-dist
COPY bootstrap/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh
ENV THESHED_FRONTEND_DIST=/app/frontend-dist
ENV THESHED_PROFILE=bootstrap
EXPOSE 8080
ENTRYPOINT ["/app/entrypoint.sh"]
