# FamilyHostel onboarding bot
# Two-bot deploy: TELEGRAM_BOT_ENV=prod or staging selects the right token.
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

# The package lives one level up so we copy parent + run as a module.
COPY . /app/bot

ENV PYTHONPATH=/app
USER 1000:1000

CMD ["python", "-m", "bot"]
