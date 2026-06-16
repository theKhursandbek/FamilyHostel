# Telegram BotFather setup — Hotel Mini App

End-to-end checklist for registering the Mini App with `@BotFather` and
wiring its webhook to your Django backend.

---

## 1. Create the bot

1. Open `@BotFather` in Telegram.
2. Send `/newbot` and pick a display name (e.g. `Hotel`) and username
   (`hotel_yourname_bot`).
3. Save the **bot token** that BotFather returns. This is your
   `TELEGRAM_BOT_TOKEN` for the backend `.env`.

## 2. Register the Mini App

1. In BotFather, send `/newapp`.
2. Choose your bot.
3. Provide:
   - **Title**: `Hotel`
   - **Short description**: `Book a room and manage your stay`
   - **Photo** (640×360 PNG/JPG)
   - **Demo GIF** (optional)
   - **Web App URL**: `https://your-domain.example.com/`
     (must be HTTPS; this is the URL Vite builds to `dist/`)
   - **Short name**: `app` → produces `t.me/<bot>/app`

## 3. Set the menu button (optional)

Make the Mini App launch from the chat menu:

```
/setmenubutton
→ choose your bot
→ "Edit menu button URL"
→ https://your-domain.example.com/
→ Button text: Open Hotel
```

## 4. Configure deep links

Deep links open the Mini App on a specific page:

```
https://t.me/<bot>/app?startapp=booking_42
https://t.me/<bot>/app?startapp=task_17
```

The Mini App reads `Telegram.WebApp.initDataUnsafe.start_param` and the
router can navigate accordingly. Update the entry point in
`src/main.jsx` to dispatch on `start_param` if you need it.

## 5. Webhook (server side)

The Django backend uses `python-telegram-bot` for outgoing messages
only. If you also want incoming updates (e.g. `/start` deep links), set
the webhook **once**:

```bash
curl -F "url=https://api.your-domain.example.com/api/v1/telegram/webhook/" \
     "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook"
```

Confirm it took effect:

```bash
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo"
```

## 6. Domains allowlist

In BotFather → `/setdomain` add the **exact** HTTPS domain that hosts
the Mini App (no trailing slash, no path). Telegram refuses to open Mini
Apps on domains it has not been told about.

## 7. Test in Telegram

1. Open `t.me/<bot>` and tap the **menu button** (or the inline button
   from `/start`).
2. The Mini App opens inside Telegram WebView with `initData` populated.
3. The backend validates the HMAC signature in
   `apps/accounts/auth_views.py` (`TelegramAuthView`) and issues JWTs.

## 8. Production env vars

| Variable                 | Where        | Notes                                  |
| ------------------------ | ------------ | -------------------------------------- |
| `TELEGRAM_BOT_TOKEN`     | backend .env | From BotFather                         |
| `TELEGRAM_BOT_USERNAME`  | backend .env | Without `@`, e.g. `hotel_yourname_bot` |
| `STRIPE_PUBLISHABLE_KEY` | backend .env | Used by `/payments/stripe/intent/`     |
| `STRIPE_SECRET_KEY`      | backend .env | Server-only                            |
| `STRIPE_WEBHOOK_SECRET`  | backend .env | From Stripe dashboard                  |
| `OPENAI_API_KEY`         | backend .env | Optional — chat falls back to canned reply if absent |
| `VITE_API_URL`           | mini-app .env | Public HTTPS API base, e.g. `https://api.example.com/api/v1` |
| `VITE_SENTRY_DSN`        | mini-app .env | Optional client error tracking         |

## 9. Troubleshooting

- **Blank screen in Telegram**: Open the Mini App URL in a regular
  browser. If it blanks there too, check the Vite build (`npm run build`)
  and the server's `Content-Security-Policy` header — it must allow
  inline scripts from `https://telegram.org`.
- **`401 Unauthorized` from `/api/v1/auth/telegram/`**: The bot token in
  the backend `.env` does not match the one used to launch the Mini App.
- **Stripe payment redirects out of Telegram**: Use the
  `redirect: "if_required"` mode (already wired in `PaymentPage.jsx`)
  and host on the **same** HTTPS domain registered with BotFather.
