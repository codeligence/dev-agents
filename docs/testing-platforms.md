# Platform Services

Besides Slack, Dev Agents can talk through **Telegram**, **Mattermost** and **Email**. They share
one rule: a platform starts only when its `<NAME>_ENABLED` flag is truthy **and** its credentials
are present.

```bash
pip install -e ".[prod]"                        # includes telegram + mattermost
pip install -e ".[telegram,mattermost]"         # or just the extras you need
```

!!! warning "Set an allowlist"
    Each platform exposes the agent — and through it your codebase — to a public messaging
    surface. Without `*_ALLOWED_USERS`, every user who can reach the bot can drive it. Set an
    allowlist for anything beyond a local test.

## Telegram

Create a bot with [@BotFather](https://t.me/BotFather) and copy the token.

```bash
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=your-bot-token
```

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_ALLOWED_USERS` | *(empty — everyone)* | Comma-separated user IDs |
| `TELEGRAM_REQUIRE_MENTION` | `true` | Require an @mention in group chats |
| `TELEGRAM_FREE_RESPONSE_CHATS` | *(empty)* | Chat IDs exempt from the mention requirement |

Your own user ID comes from [@userinfobot](https://t.me/userinfobot).

## Mattermost

Create a bot account under **Integrations → Bot Accounts** (or use a personal access token) and
copy the token.

```bash
MATTERMOST_ENABLED=true
MATTERMOST_URL=https://mattermost.example.com
MATTERMOST_TOKEN=your-token
```

`MATTERMOST_URL` must be `https://` — the token travels over the REST and WebSocket connections.
For a plaintext local server, set `MATTERMOST_ALLOW_INSECURE=true`.

| Variable | Default | Description |
|----------|---------|-------------|
| `MATTERMOST_ALLOWED_USERS` | *(empty — everyone)* | Comma-separated user IDs |
| `MATTERMOST_REQUIRE_MENTION` | `true` | Require an @mention in channels |
| `MATTERMOST_FREE_RESPONSE_CHANNELS` | *(empty)* | Channel IDs exempt from the mention requirement |
| `MATTERMOST_REPLY_MODE` | `off` | `thread` nests replies |
| `MATTERMOST_ALLOW_INSECURE` | `false` | Allow a plaintext `http://` URL (local dev only) |

## Email

Use a mailbox with IMAP and SMTP access. For Gmail, create an
[App Password](https://myaccount.google.com/apppasswords) (requires 2FA).

```bash
EMAIL_ENABLED=true
EMAIL_ADDRESS=bot@example.com
EMAIL_PASSWORD=your-app-password
EMAIL_IMAP_HOST=imap.example.com
EMAIL_SMTP_HOST=smtp.example.com
```

All four IMAP/SMTP values are required.

| Variable | Default | Description |
|----------|---------|-------------|
| `EMAIL_IMAP_PORT` | `993` | IMAP port |
| `EMAIL_SMTP_PORT` | `587` | SMTP port |
| `EMAIL_POLL_INTERVAL` | `15` | Seconds between mailbox polls |
| `EMAIL_ALLOWED_USERS` | *(empty — everyone)* | Comma-separated sender addresses |
| `EMAIL_VERIFY_DKIM` | `true` | Require a DKIM signature aligned with `From:`; disable only behind an authenticating gateway |

The bot polls for new mail and replies over SMTP. Automated and no-reply senders are ignored.

### Sender authentication

Incoming mail must carry a valid DKIM signature whose signing domain aligns with the `From:`
domain, checked before `EMAIL_ALLOWED_USERS`. A `From:` header is trivially forgeable — without
this the allowlist authenticates nothing. `EMAIL_VERIFY_DKIM` defaults to `true`; set it to
`false` only when an upstream gateway already authenticates senders. The service refuses to start
with verification on but `dkimpy` missing, rather than silently accepting unauthenticated mail.

DKIM verification needs the `email` extra (included in `[prod]`):

```bash
pip install -e ".[email]"
```

## Running several at once

Platforms are independent — enable any combination and they start together with Slack and the
other entrypoints. Verify what was picked up in the startup logs:

```
Configured services: ['slack', 'platforms']
Detected platforms: telegram, email
```

Run `dev-agents -v` for verbose logging.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `No additional platforms detected` | `<NAME>_ENABLED=true` and the credentials must both be set and visible to the process |
| Mattermost refuses to start, "must use https://" | Use an `https://` URL, or `MATTERMOST_ALLOW_INSECURE=true` for local dev |
| Mattermost WebSocket keeps disconnecting | Check the token's permissions and the URL (no trailing slash) |
| Telegram `409 Conflict` | Another instance is polling with the same token |
| Email connection refused | Verify host and port, and that the network allows the connection |
| `ModuleNotFoundError: telegram` / `aiohttp` | `pip install -e ".[telegram]"` / `".[mattermost]"` |
