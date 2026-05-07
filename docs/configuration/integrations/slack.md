# Slack Integration

Integrate Dev Agents with Slack to interact with your AI assistant directly from your team channels.

## Slack App Setup

### Step 1: Create Slack App

1. Go to [https://api.slack.com/apps](https://api.slack.com/apps)
2. Click **"Create New App"**
3. Select **"From scratch"**
4. Choose an app name (e.g., "Dev Agents")
5. Select your Slack workspace

### Step 2: Configure App Permissions

The fastest path is to import the bundled manifest at
`src/integrations/slack/manifest.json` (App settings → **App Manifest**).
If you wire it up by hand instead, add these Bot Token Scopes under
**OAuth & Permissions**:

#### Required Scopes
```
app_mentions:read       # Listen to @mentions
assistant:write         # Required for Agents & AI Apps (Assistant container, set_title, set_suggested_prompts)
canvases:read           # Read canvases
canvases:write          # Create canvases for long-form attachments
channels:history        # Read public channel history
channels:manage         # Manage canvas access on channels
channels:read           # List channels
chat:write              # Send messages
chat:write.customize    # Customize bot username / avatar per message
chat:write.public       # Send messages to public channels without joining
commands                # Reserved for future slash commands
files:read              # Read uploaded files (attachments)
files:write             # Upload files
groups:history          # Read private channel history
groups:read             # List private channels
im:history              # Read DM history
reactions:read          # Read reactions (eyes-emoji status)
reactions:write         # Add the 👀 status reaction while processing
users:read              # Resolve user IDs → real names
```

### Step 3: Enable Socket Mode

1. Go to **Socket Mode**
2. Enable Socket Mode
3. Generate an App-Level Token with `connections:write` scope
4. Save the token (starts with `xapp-`)

### Step 4: Configure Event Subscriptions

In **Event Subscriptions**:

1. Enable Events
2. Subscribe to these Bot Events:
   ```
   app_mention                          # @mentions
   message.channels                     # Messages in public channels
   message.groups                       # Messages in private channels
   message.im                           # Direct messages
   assistant_thread_started             # Required by Agents & AI Apps — fires when a user opens the assistant side panel
   assistant_thread_context_changed     # Required by Agents & AI Apps — fires when the user navigates between channels
   ```

### Step 5: Enable Agents & AI Apps

The Assistant container (top-bar entry, side-panel chat, history tabs)
requires the **Agents & AI Apps** feature toggle:

1. Go to **Agents & AI Apps** in the App settings
2. Enable the feature
3. Confirm `assistant:write` is granted (Step 2) and the two
   `assistant_thread_*` events are subscribed (Step 4)

The bundled manifest sets `features.assistant_view` so this toggle is
already on for fresh installs.

### Step 6: Install App

1. Go to **Install App**
2. Install to your workspace
3. Copy the **Bot User OAuth Token** (starts with `xoxb-`)

## Environment Configuration

Add these to your `.env` file:

```bash
# Slack Integration (Socket Mode — no signing secret needed)
SLACK_BOT_TOKEN=xoxb-your-bot-user-oauth-token
SLACK_APP_TOKEN=xapp-your-app-level-token

# Optional: bypass mention check (always respond)
ALWAYS_RESPOND=false

# Optional: per-thread processing timeout in seconds
SLACK_PROCESSING_TIMEOUT=6000
```

## Configuration File

The defaults live in `src/core/defaults/config.yaml`. Override per
deployment in `config/config.yaml` or via environment variables:

```yaml
slack:
  bot:
    botToken:    "@jinja {{ env.SLACK_BOT_TOKEN or '' }}"
    appToken:    "@jinja {{ env.SLACK_APP_TOKEN or '' }}"
    processingTimeout: 6000   # per-thread timeout (seconds)
    alwaysRespond: false      # respond without an @mention

  assistant:
    welcomeMessage: "Hi! Ask me anything about the codebase, pull requests, or work items."
    includeFeedbackButtons: true
    suggestedPrompts:
      - title: "Write testing notes"
        message: "Write testing notes for work item <id>"
      - title: "Analyze a pull request"
        message: "Analyze the changes in PR <id>"
```

`slack.assistant.suggestedPrompts` populates the prompt chips Slack
shows when a user opens a fresh Assistant thread. Different deployments
can list a different set so each environment surfaces its own skills.

## Starting the Slack Bot

### Development Mode

```bash
# Activate virtual environment
source venv/bin/activate

# Start the Slack bot
python -m entrypoints.slack_entrypoint.service
```

### Production Mode

```bash
# Set environment and start
ENV_FOR_DYNACONF=production python -m entrypoints.slack_entrypoint.service
```

## Usage Examples

### Basic Commands

```slack
# In any channel or DM
@BettySharp analyze the latest changes

@BettySharp help me understand the authentication flow

@BettySharp what tests should I write for PR #123?
```

### Advanced Interactions

```slack
# Code analysis
@BettySharp review the changes in commit abc123

# Testing notes generation
@BettySharp generate testing notes for refactoring the payment system

# Release planning
@BettySharp generate release notes for sprint 42
```

## Channel Management

### Adding the Bot to Channels

1. **Invite to channel**: `/invite @BettySharp`
2. **Public channels**: Bot can be mentioned once invited
3. **Private channels**: Requires explicit invitation

### Channel Permissions

The bot will:
- ✅ Respond to @mentions in any channel it's in
- ✅ Answer direct messages
- ✅ Read conversation context for better responses
- ❌ Never post unsolicited messages
- ❌ Never react to messages unless mentioned

## Assistant Container (Agents & AI Apps)

When **Agents & AI Apps** is enabled (Step 5), the bot also surfaces
inside Slack's Assistant side panel:

- **Top-bar entry point** — the bot icon appears in the workspace's main
  navigation.
- **Suggested prompts** — opening a fresh Assistant thread shows the
  prompt chips listed under `slack.assistant.suggestedPrompts`.
- **Welcome message** — the first user prompt is preceded by
  `slack.assistant.welcomeMessage` (set to an empty string to suppress).
- **Thread titles** — the bot derives a title (≤100 chars) from the
  user's first message so the History tab is browseable.
- **Channel context** — when the user navigates to a different channel,
  Slack fires `assistant_thread_context_changed` which the bot persists.

Status updates inside an Assistant thread keep the existing channel
behaviour: a real Slack message is posted and updated in place as the
agent makes progress (no ephemeral typing indicator). In channel
`@mentions` the bot also adds a 👀 reaction to the latest message while
processing and removes it when done.

## Feedback Buttons

Every final response (and canvas permalink message) is appended with
native thumbs-up / thumbs-down `feedback_buttons`. Clicks are handled by
the `agent_response_feedback` action and written as one-line structured
JSON to the dedicated `dev_agents.slack.feedback` logger:

```json
{"event":"slack_feedback","ts":"2026-04-08T12:00:00+00:00","user_id":"U123","channel_id":"C456","thread_ts":"1234.5678","message_ts":"1234.9999","value":"positive","action_id":"agent_response_feedback"}
```

The logger writes to stdout so any log aggregator (Datadog, Loki, etc.)
can ingest it without parsing the human-readable application log. To
hide the buttons entirely, set `slack.assistant.includeFeedbackButtons:
false` in your config.

## Threading and Context

### Thread Behavior

Dev Agents maintains conversation context:

```slack
You: @BettySharp analyze this PR
Bot: I'll analyze PR #123. Here's what I found... [thread]
You: What about security implications? [in thread]
Bot: For security, I notice... [continues in thread]
```

### Context Awareness

The bot understands:
- **Previous messages** in the thread
- **File attachments** and links
- **User mentions** and relationships
- **Channel topic** and purpose

## Troubleshooting

### Common Issues

#### Bot Not Responding

Check these items:

```bash
# 1. Verify tokens are set
echo $SLACK_BOT_TOKEN | head -c 10
echo $SLACK_APP_TOKEN | head -c 10

# 2. Check bot is running
ps aux | grep slack_entrypoint

# 3. Verify permissions
# Bot needs to be in the channel where you're messaging
```

#### Permission Errors

```bash
# Check OAuth scopes in Slack App settings
# Reinstall app if scopes were added after installation
```

#### Connection Issues

```bash
# Test network connectivity
curl -X POST https://slack.com/api/auth.test \
  -H "Authorization: Bearer $SLACK_BOT_TOKEN"
```

### Debug Mode

Enable debug logging:

```bash
# Set debug level
export LOG_LEVEL=DEBUG

# Start with verbose output
DEV_AGENTS_CONSOLE_LOGGING=1 python -m entrypoints.slack_entrypoint.service
```

## Security Considerations

### Token Security

- **Never commit tokens** to version control
- **Use environment variables** for all secrets
- **Rotate tokens** periodically
- **Limit app permissions** to minimum required

### Message Privacy

Dev Agents:
- **Reads messages** only when mentioned or in DMs
- **Doesn't store** conversation history persistently
- **Processes locally** or via configured AI service
- **Respects** Slack's data retention policies

## Best Practices

1. **Clear naming** - Use descriptive agent names (@BettySharp)
2. **Channel organization** - Dedicate channels for dev discussions
3. **Thread usage** - Keep related conversations in threads
4. **Context sharing** - Include relevant links and details
5. **Team training** - Help team members learn effective prompts

## Advanced Configuration

### Custom Responses

Modify prompts in `config/prompts.yaml`:

```yaml
slack:
  messages:
    greeting: |
      👋 Hi! I'm {agent_name}, your development assistant.
      
      I can help with:
      • Code analysis and reviews
      • Testing notes generation
      • Testing recommendations
      • Documentation questions
      
      Just @mention me with your question!
```

### Multi-Workspace Setup

For multiple Slack workspaces:

```yaml
integrations:
  slack:
    workspaces:
      - name: "team-alpha"
        bot_token: "${SLACK_ALPHA_BOT_TOKEN}"
        app_token: "${SLACK_ALPHA_APP_TOKEN}"
      - name: "team-beta" 
        bot_token: "${SLACK_BETA_BOT_TOKEN}"
        app_token: "${SLACK_BETA_APP_TOKEN}"
```

## Next Steps

- Configure [Azure DevOps integration](azure-devops.md)
- Set up [GitLab integration](gitlab.md)
- Customize [prompts](../prompts-yaml.md) for your team