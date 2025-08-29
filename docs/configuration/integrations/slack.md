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

Navigate to **OAuth & Permissions** and add these Bot Token Scopes:

#### Required Scopes
```
app_mentions:read      # Listen to @mentions
chat:write            # Send messages
chat:write.public     # Send messages to public channels
channels:history      # Read message history
channels:read         # List channels
groups:history        # Read private channel history
groups:read           # List private channels
im:history            # Read DM history
im:read               # List DMs
mpim:history          # Read group DM history
mpim:read             # List group DMs
users:read            # Read user information
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
   app_mention          # When someone @mentions the bot
   message.channels     # Messages in channels bot is in
   message.groups       # Messages in private channels
   message.im           # Direct messages
   message.mpim         # Group direct messages
   ```

### Step 5: Install App

1. Go to **Install App**
2. Install to your workspace
3. Copy the **Bot User OAuth Token** (starts with `xoxb-`)

## Environment Configuration

Add these to your `.env` file:

```bash
# Slack Integration
SLACK_BOT_TOKEN=xoxb-your-bot-user-oauth-token
SLACK_APP_TOKEN=xapp-your-app-level-token
SLACK_SIGNING_SECRET=your-signing-secret

# Optional: Agent identity in Slack
AGENT_NAME=BettySharp
```

## Configuration File

Add to your `config/config.yaml`:

```yaml
integrations:
  slack:
    enabled: true
    mock_mode: false
    
    # Optional: Restrict to specific channels
    channels:
      - "#development"
      - "#devops" 
      - "#code-review"
    
    # Optional: Slack-specific settings
    settings:
      thread_replies: true      # Reply in threads by default
      mention_required: false   # Respond without @mention in DMs
      typing_indicator: true    # Show typing indicator
```

## Starting the Slack Bot

### Development Mode

```bash
# Activate virtual environment
source venv/bin/activate

# Start the Slack bot
python -m src.entrypoints.slack_bot
```

### Production Mode

```bash
# Set environment and start
ENV_FOR_DYNACONF=production python -m src.entrypoints.slack_bot
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

# Impact analysis  
@BettySharp analyze impact of refactoring the payment system

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
ps aux | grep slack_bot

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
python -m src.entrypoints.slack_bot --verbose
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
      • Impact assessment
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