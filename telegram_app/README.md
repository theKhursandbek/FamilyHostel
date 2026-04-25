# FamilyHostel — Telegram Mini App

Companion mobile experience to the FamilyHostel admin panel.

## Audience

| User      | What they see                                                     |
| --------- | ----------------------------------------------------------------- |
| Anonymous | Public branch list, room galleries — no sign-in required.         |
| Client    | Above + their bookings, profile.                                  |
| Staff     | Personal dashboard: cleaning tasks, days off, penalties.          |

The app reads `window.Telegram.WebApp.initData` (provided by Telegram when
opened via a bot button or `t.me/<bot>/<webapp>` link) and exchanges it
against `POST /api/v1/auth/telegram/` for a JWT pair.

When opened in a regular desktop browser **outside** Telegram, the app stays
in **demo mode**: public pages still work; if `VITE_DEV_FALLBACK_LOGIN=true`,
a phone+password sign-in button is shown so the staff/client UI can be
exercised without a real Telegram bot.

## Run

```powershell
cd telegram_app
copy .env.example .env
npm install
npm run dev
```

Open http://localhost:5174 in a browser, or open the deployed URL inside
Telegram via your bot's MenuButton / BotFather WebApp.

## Backend endpoints used

- Public  — `GET /api/v1/public/branches/`, `GET /api/v1/public/rooms/`
- Auth    — `POST /api/v1/auth/telegram/` (Telegram), `POST /api/v1/auth/login/` (demo)
- Client  — `GET /api/v1/bookings/bookings/?client=me`
- Staff   — `GET /api/v1/cleaning/tasks/?assigned_to=me`,
            `GET /api/v1/staff/days-off/`, `GET /api/v1/penalties/`

## Project structure

```
src/
├── components/        Telegram-aware UI primitives (BackButton, BottomNav…)
├── context/           AuthContext + Telegram WebApp wrapper
├── pages/             Route components grouped by audience
│   ├── public/        Browse branches & rooms (no auth)
│   ├── client/        After Telegram login as a client
│   └── staff/         After Telegram login as staff
├── services/          axios + per-resource API clients
└── App.jsx            Router, auth guards
```
