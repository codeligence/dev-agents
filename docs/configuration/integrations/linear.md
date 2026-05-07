# Linear Integration

Connect Dev Agents with Linear to analyze issues, track work items, and provide project management insights directly from your chat platform.

## Linear Setup

### Step 1: Create API Key

1. Go to [Linear Settings](https://linear.app/settings)
2. Navigate to **Security & Access → API**
3. Click **Create key**
4. Give it a descriptive label (e.g., `Dev Agents Integration`)
5. Copy the API key immediately (starts with `lin_api_`)

> **Note:** Linear API keys are scoped to the user who creates them. The integration will have the same access as the user.

### Step 2: Gather Information

No additional information is needed beyond the API key. Linear's GraphQL API automatically provides access to all teams, projects, and issues the authenticated user can see.

## Environment Configuration

Add to your `.env` file:

```bash
# Linear Integration
LINEAR_API_KEY=lin_api_your-api-key-here
```

## Configuration File

Add to your project's `config.yaml`:

```yaml
projects:
  my_project:
    git:
      path: "/path/to/repo"
    issues:
      linear:
        api_key: "@jinja {{env.LINEAR_API_KEY}}"
```

### Mock Mode

For testing without Linear access:

```yaml
projects:
  my_project:
    issues:
      linear:
        mock: true
```

## Features

### Issue Analysis

Analyze Linear issues for requirements understanding, testing recommendations, and implementation planning:

```slack
@DevAgent analyze issue ENG-123

@DevAgent what tests should I write for ENG-456?

@DevAgent summarize the requirements in TEAM-789
```

### Automatic Issue Detection

Dev Agents automatically detects Linear issue identifiers (e.g., `ENG-123`, `TEAM-456`) in conversations and can fetch context when needed. Issue identifiers follow the `TEAMKEY-NUMBER` pattern.

### Issue Context

When loading an issue, Dev Agents retrieves:

- **Title and description** (Markdown)
- **State** (workflow state like Backlog, In Progress, Done)
- **Priority** (Urgent, High, Medium, Low)
- **Assignee and creator**
- **Team, project, and cycle**
- **Labels**
- **Estimate and due date**
- **Parent and sub-issues**
- **Comments** with author and timestamp

## Multiple Issue Trackers

Linear can be configured alongside other issue providers (GitLab, Jira). The first configured provider that matches will be used:

```yaml
projects:
  my_project:
    issues:
      linear:
        api_key: "@jinja {{env.LINEAR_API_KEY}}"
      jira:
        domain: "company"
        email: "user@company.com"
        token: "@jinja {{env.JIRA_TOKEN}}"
```

## Testing and Validation

### Test Connection

Verify your Linear integration by loading an issue in mock mode first, then with your real API key:

```bash
# Test with mock mode
# Set mock: true in your config and verify the agent responds with mock data

# Test API connectivity
curl -X POST https://api.linear.app/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: $LINEAR_API_KEY" \
  -d '{"query": "{ viewer { id name email } }"}'
```

### Mock Mode

Mock mode uses local JSON fixtures to simulate Linear API responses. This is useful for:

- Development and testing without API access
- CI/CD pipelines
- Demos and presentations

## Troubleshooting

### Common Issues

#### Authentication Failed

```bash
# Verify your API key is valid
curl -X POST https://api.linear.app/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: $LINEAR_API_KEY" \
  -d '{"query": "{ viewer { id name } }"}'
```

If you receive a 401 error, your API key may be invalid or expired. Generate a new one from Linear Settings.

#### Issue Not Found

Linear issue identifiers are case-insensitive but must follow the `TEAMKEY-NUMBER` format. Ensure:

- The team key exists in your Linear workspace
- The issue number is valid
- The authenticated user has access to the team

#### Rate Limiting

Linear allows 5,000 requests per hour per user. If you hit rate limits:

- Reduce polling frequency
- Use webhooks for real-time updates instead of polling
- Monitor `X-RateLimit-Requests-Remaining` response headers

## Security Considerations

### API Key Security

- **Environment variables** — Store API keys in `.env` file only, never in config files
- **Minimal access** — API keys inherit the creating user's permissions; consider using a dedicated service account
- **Regular rotation** — Regenerate API keys periodically

### Data Access

Dev Agents accesses:
- Issue metadata (title, description, state, priority)
- Comments and discussions
- Team and project information
- User information (name, email)
- No modification of Linear data (read-only)

## Best Practices

1. **Descriptive issues** — Write clear issue descriptions with acceptance criteria for better AI analysis
2. **Consistent labeling** — Use consistent labels across teams for reliable filtering
3. **Link issues** — Reference Linear issue IDs in commit messages and PR descriptions
4. **Use sub-issues** — Break down large issues for better tracking and analysis

## API Reference

Dev Agents uses the Linear GraphQL API:

- **API Endpoint**: `https://api.linear.app/graphql`
- **Authentication**: API key in `Authorization` header
- **Schema Explorer**: [Linear API Schema](https://studio.apollographql.com/public/Linear-API/variant/current/schema/reference)
- **Developer Docs**: [Linear Developers](https://linear.app/developers)
