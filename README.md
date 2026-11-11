# 🎯 VideoAI Telegram Subscription Bot

A fully Amharic-language Telegram bot for managing web service subscriptions with multi-email pricing, CBE/Telebirr payment flow, screenshot verification, and admin-controlled service link delivery.

---

## ✨ Features

- 🌟 Rich welcome screen with inline Start button
- 📧 Choose 1–10 emails with live pricing (490 ETB base + 50 ETB per extra)
- 📋 Order summary/confirmation step before payment
- 💳 CBE Bank or Telebirr payment options
- 📸 Payment screenshot upload
- 🔔 Instant admin notification with screenshot
- 📖 Auto-send instruction image after verification
- 🇪🇹 Full Amharic user interface

---

## 💰 Pricing

| Emails | Price (ETB) |
|--------|-------------|
| 1      | 490         |
| 2      | 540         |
| 3      | 590         |
| n      | 490 + (n−1) × 50 |

---

## 🗂 Project Structure

```
AI_telegram_bot/
├── bot.py            # Main bot + conversation flow (Amharic UI)
├── admin.py          # Admin commands
├── database.py       # Async SQLite layer
├── config.py         # Settings from .env
├── requirements.txt
├── render.yaml       # Render deployment config
├── Procfile          # Fallback start command
├── runtime.txt       # Python version pin
├── .env              # ⚠️  Your secrets — never commit this
└── .env.example      # Safe template to share
```

---

## 🚀 Local Setup

### 1. Create a virtual environment
```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment variables
```bash
copy .env.example .env       # Windows
# cp .env.example .env       # macOS/Linux
```

Edit `.env` and fill in your values:

| Variable           | Description                                      |
|--------------------|--------------------------------------------------|
| `BOT_TOKEN`        | Token from [@BotFather](https://t.me/BotFather)  |
| `ADMIN_IDS`        | Comma-separated Telegram user IDs of admins      |
| `CBE_ACCOUNT`      | Your CBE bank account number                     |
| `TELEBIRR_ACCOUNT` | Your Telebirr phone number                       |
| `ACCOUNT_NAME`     | Account holder name shown to users               |
| `DB_PATH`          | SQLite file path (default: `subscriptions.db`)   |

> **Tip:** Find your Telegram user ID by messaging [@userinfobot](https://t.me/userinfobot).

### 4. Run locally
```bash
python bot.py
```

---

## ☁️ Deploy to Render

### Step 1 — Push to GitHub
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

### Step 2 — Create a Render Worker
1. Go to [render.com](https://render.com) and sign in
2. Click **New → Background Worker**
3. Connect your GitHub repo
4. Render auto-detects `render.yaml` — click **Apply**

### Step 3 — Set Environment Variables
In the Render dashboard → your service → **Environment**:

| Key                | Value                        |
|--------------------|------------------------------|
| `BOT_TOKEN`        | Your bot token               |
| `ADMIN_IDS`        | e.g. `123456789`             |
| `CBE_ACCOUNT`      | Your CBE account number      |
| `TELEBIRR_ACCOUNT` | Your Telebirr number         |
| `ACCOUNT_NAME`     | Account holder name          |
| `DB_PATH`          | `/data/subscriptions.db`     |

> ⚠️ **Never** put your real `.env` file on GitHub. Set all secrets through the Render dashboard only.

### Step 4 — Persistent Disk
`render.yaml` already configures a 1 GB disk mounted at `/data`.
The SQLite database is stored at `/data/subscriptions.db` and survives restarts/redeploys.

### Step 5 — Deploy
Click **Deploy** — Render installs dependencies and starts the bot. Check **Logs** to confirm:
```
Database initialised.
Bot is running…
```

---

## 🛠 Admin Commands

| Command                        | Description                                           |
|-------------------------------|-------------------------------------------------------|
| `/pending`                    | List all pending (unverified) orders                  |
| `/orderinfo <id>`             | View full details + payment screenshot                |
| `/verify <id> <link>`         | Approve order → sends link + instruction image to user|
| `/reject <id>`                | Reject order → notifies user                          |
| `/setinstruction`             | Set instruction image (send photo with this caption)  |
| `/clearinstruction`           | Remove saved instruction image                        |
| `/previewinstruction`         | Preview the current instruction image                 |

---

## 👤 User Commands

| Command      | Description                          |
|--------------|--------------------------------------|
| `/start`     | Open welcome screen                  |
| `/mystatus`  | View your orders and their status    |
| `/cancel`    | Cancel the current subscription flow |

---

## 🔄 User Flow

```
/start
  └─▶ Welcome screen  [🚀 ምዝገባ ጀምር]
        └─▶ Step 1: Choose email count (1–10, price shown per option)
              └─▶ Step 2: Enter each email address one by one
                    └─▶ Step 3: Order summary — confirm or edit
                          └─▶ Step 4: Choose payment (CBE / Telebirr)
                                └─▶ Step 5: Send payment screenshot
                                      └─▶ Admin notified instantly
                                            └─▶ Admin runs /verify → user gets link + instructions
```
