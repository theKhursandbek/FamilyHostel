# ==============================================================================
# Stage 1 — Build dependencies
# ==============================================================================
FROM python:3.11-slim AS builder

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies required by psycopg2, Pillow
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        libjpeg62-turbo-dev \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies into a virtual env for clean copy
COPY requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# ==============================================================================
# Stage 2 — Production runtime
# ==============================================================================
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production \
    PATH="/opt/venv/bin:$PATH"

# Runtime system libs (no compiler)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        libjpeg62-turbo \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN addgroup --system django \
    && adduser --system --ingroup django django

WORKDIR /app

# Copy virtual env from builder
COPY --from=builder /opt/venv /opt/venv

# Copy project source code
COPY . .

# Collect static files (SECRET_KEY needed at build time only for collectstatic)
RUN SECRET_KEY=build-placeholder \
    DB_NAME=x DB_USER=x DB_PASSWORD=x DB_HOST=x DB_PORT=5432 \
    python manage.py collectstatic --noinput

# Make entrypoint executable
RUN chmod +x /app/entrypoint.sh

# Ownership to non-root user
RUN chown -R django:django /app

USER django

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
