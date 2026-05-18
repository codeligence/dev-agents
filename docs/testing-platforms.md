# Manual Testing: Platform Services

How to run dev-agents with Email, Mattermost, and Telegram platforms.

## Prerequisites

```bash
pip install -e ".[prod,telegram,mattermost]"
```

## Telegram

### Setup

1. Create a bot via [@BotFather](https://t.me/BotFather) on Telegram
2. Copy the bot token
3. Add to `.env`:

```env
TELEGRAM_BOT_TOKEN=your-bot-token-here
```

### Optional settings

```env
# Only allow specific users (comma-separated Telegram user IDs)
TELEGRAM_ALLOWED_USERS=123456789,987654321

# Require @mention in group chats (default: false)
TELEGRAM_REQUIRE_MENTION=true

# Chat IDs where bot responds without @mention
TELEGRAM_FREE_RESPONSE_CHATS=chat_id_1,chat_id_2
```

### Test it

```bash
dev-agents
```

Then message your bot on Telegram. It should respond via the gitchatbot agent.

To find your Telegram user ID, message [@userinfobot](https://t.me/userinfobot).

---

## Mattermost

### Setup

1. In Mattermost, go to **Integrations > Bot Accounts** and create a bot (or use a personal access token under **Profile > Security**)
2. Copy the token
3. Add to `.env`:

```env
MATTERMOST_URL=https://your-mattermost-server.com
MATTERMOST_TOKEN=your-bot-token-here
```

### Optional settings

```env
# Reply in threads instead of flat messages (default: off)
MATTERMOST_REPLY_MODE=thread

# Require @mention in channels (default: true)
MATTERMOST_REQUIRE_MENTION=true

# Channels where bot responds without @mention
MATTERMOST_FREE_RESPONSE_CHANNELS=channel_id_1,channel_id_2

# Only allow specific users (comma-separated Mattermost user IDs)
MATTERMOST_ALLOWED_USERS=user_id_1,user_id_2
```

### Test it

```bash
dev-agents
```

Mention the bot in a channel or send it a DM. It should respond via the gitchatbot agent.

---

## Email

### Setup

1. Use an email account with IMAP/SMTP access
2. For Gmail: create an [App Password](https://myaccount.google.com/apppasswords) (requires 2FA enabled)
3. Add to `.env` (all four variables are required — email is only activated when
   the full IMAP/SMTP configuration is present):

```env
EMAIL_ADDRESS=your-bot@gmail.com
EMAIL_PASSWORD=your-app-password

# Required — use your provider's hosts. Gmail example:
EMAIL_IMAP_HOST=imap.gmail.com
EMAIL_SMTP_HOST=smtp.gmail.com
```

### Optional settings

```env
# Custom ports (defaults: IMAP=993, SMTP=587)
EMAIL_IMAP_PORT=993
EMAIL_SMTP_PORT=587

# Polling interval in seconds (default: 15)
EMAIL_POLL_INTERVAL=30

# Only allow specific senders
EMAIL_ALLOWED_USERS=alice@example.com,bob@example.com
```

### Test it

```bash
dev-agents
```

Send an email to the configured address. The bot polls for new messages and replies via SMTP.

Note: automated/noreply senders are automatically ignored.

---

## Running Multiple Platforms

All platforms auto-detect from environment variables. Set env vars for any combination and they all start together:

```bash
# Example: Slack + Telegram + Email
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
TELEGRAM_BOT_TOKEN=...
EMAIL_ADDRESS=...
EMAIL_PASSWORD=...
```

```bash
dev-agents
```

Check the logs for which platforms were detected:

```
Configured services: ['slack', 'platforms']
Detected platforms: telegram, email
```

## Verbose Logging

For debugging, run with `-v`:

```bash
dev-agents -v
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `No additional platforms detected` | Check env vars are set in `.env` or exported |
| Telegram 409 conflict | Another bot instance is running with the same token - stop it |
| Email connection refused | Verify IMAP/SMTP host and port; check firewall/VPN |
| Mattermost WebSocket disconnects | Check token permissions and server URL (no trailing slash) |
| `ModuleNotFoundError: telegram` | Run `pip install -e ".[telegram]"` |
| `ModuleNotFoundError: aiohttp` | Run `pip install -e ".[mattermost]"` |
