# Slack Integration

Slack is the primary entrypoint. It runs over **Socket Mode**, so Dev Agents needs no public URL,
no ingress and no signing secret — just two tokens.

## Create the app

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From an app
   manifest**, pick your workspace, and paste the manifest shipped in the repository:
   `src/integrations/slack/manifest.json`.
2. **Basic Information → App-Level Tokens**: generate a token with the `connections:write` scope.
   This is your `SLACK_APP_TOKEN` (`xapp-…`).
3. **Install App** into the workspace, then copy the **Bot User OAuth Token**. This is your
   `SLACK_BOT_TOKEN` (`xoxb-…`).
4. Invite the bot to the channels it should work in: `/invite @DevAgents`.

The manifest already enables Socket Mode and interactivity, subscribes to `app_mention`,
`message.channels`, `message.groups`, `message.im`, `assistant_thread_started` and
`assistant_thread_context_changed`, and requests the bot scopes the bot needs — among them
`chat:write`, `channels:history`, `groups:history`, `im:history`, `app_mentions:read`,
`assistant:write`, `files:read`, `files:write`, `canvases:read`, `canvases:write`,
`reactions:read`, `reactions:write` and `users:read`.

If you add scopes later, reinstall the app.

## Configuration

```bash
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
```

Both must be set — the Slack service starts only when it finds them. Optional settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `SLACK_PROCESSING_TIMEOUT` | `6000` | Per-thread processing timeout in seconds |
| `ALWAYS_RESPOND` | `false` | Reply in channels without being mentioned |
| `SLACK_INCLUDE_FEEDBACK_BUTTONS` | `false` | Append 👍/👎 buttons to final responses |
| `SLACK_ATTACHMENTS_ENABLED` | `false` | Forward uploaded files into the LLM context |
| `SLACK_ATTACHMENT_MAX_SIZE_MB` | `25` | Max attachment size |
| `SLACK_ATTACHMENT_MAX_INLINE_TEXT_KB` | `50` | Max inlined text per attachment |

Assistant-pane behaviour lives under `slack.assistant` in
[config.yaml](../config-yaml.md#slack): `welcomeMessage`, `includeFeedbackButtons`, and the
`suggestedPrompts` list of `{title, message}` pairs.

## Using it

```
@DevAgents how does the authentication flow work?
@DevAgents what changed in the payment module this sprint?
@DevAgents analyze PR 4711
```

- Works in channels, private groups and DMs, and in the **Agents & AI Apps** assistant pane.
  Both paths behave identically.
- Replies stay in the thread; the thread is the conversation context.
- While the agent works it adds an 👀 reaction and posts a status message it edits in place.
- Long answers are posted as a Slack **canvas** with a permalink in the thread.
- Send `stop` in the thread to cancel the in-flight run.
- Feedback button clicks are logged as structured JSON and fire the `slack.feedback`
  [hook](../hooks/index.md).

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Bot never replies | Both tokens set; bot invited to the channel; logs show `slack` among the configured services (`dev-agents -v`) |
| Replies only on mention | Expected — set `ALWAYS_RESPOND=true` to change it |
| `missing_scope` errors | Add the scope in the app config and **reinstall** the app |
| No Socket Mode connection | The app-level token needs `connections:write`, and Socket Mode must be enabled |
| Uploaded files ignored | `SLACK_ATTACHMENTS_ENABLED=true` (off by default on purpose) |

## Notes

- Message content and attached files are sent to your LLM provider. Attachment forwarding is
  opt-in for that reason.
- Tokens grant workspace access — keep them in a secret store and rotate them if leaked.

## Next steps

- [Environment variables](../environment-variables.md#slack)
- [config.yaml](../config-yaml.md#slack)
- [Hooks](../hooks/index.md) — customize feedback blocks, register tools
