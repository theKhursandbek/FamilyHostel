# FamilyHostel onboarding bot

Aiogram-style conversation flow that brings new clients into the Mini App
(see [TELEGRAM_MINI_APP_PLAN.md](../../TELEGRAM_MINI_APP_PLAN.md) §3.1).

```
/start  →  pick language  →  share phone  →  receive SMS code  →  type code  →  Open Mini App
```

## Env vars

| Variable | Required | Notes |
|----------|----------|-------|
| `TELEGRAM_BOT_ENV` | yes | `prod` or `staging` |
| `TELEGRAM_BOT_TOKEN_PROD` | when env=prod | from BotFather |
| `TELEGRAM_BOT_TOKEN_STAGING` | when env=staging | separate BotFather bot |
| `BACKEND_API_URL` | yes | e.g. `https://api.familyhostel.uz/api/v1` |
| `MINI_APP_URL` | yes | full https URL incl. `?env=prod` |
| `MINI_APP_SHORT_NAME` | yes | WebApp short name set in BotFather |
| `LOG_LEVEL` | optional | default `INFO` |

## Local run

```pwsh
$env:TELEGRAM_BOT_ENV="staging"
$env:TELEGRAM_BOT_TOKEN_STAGING="<token>"
$env:BACKEND_API_URL="http://localhost:8000/api/v1"
$env:MINI_APP_URL="https://example.com/?env=staging"
pip install -r requirements.txt
python -m bot
```

## Docker

```pwsh
docker build -t familyhostel-bot .
docker run --rm `
  -e TELEGRAM_BOT_ENV=staging `
  -e TELEGRAM_BOT_TOKEN_STAGING=<token> `
  -e BACKEND_API_URL=https://api.familyhostel.uz/api/v1 `
  -e MINI_APP_URL=https://mini.familyhostel.uz/?env=staging `
  familyhostel-bot
```
