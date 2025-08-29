# GitLab Integration

Connect Dev Agents with GitLab to analyze merge requests, issues, and project activities for comprehensive development insights.

## GitLab Setup

### Step 1: Create Personal Access Token

1. Go to your GitLab instance (gitlab.com or self-hosted)
2. Navigate to **User Settings → Access Tokens**
3. Click **Add new token**
4. Configure the token:
   - **Token name**: `Dev Agents Integration`
   - **Expiration date**: Choose appropriate duration
   - **Select scopes**: Check these permissions:

#### Required Scopes
```
api                    # Full API access
read_user             # Read user information
read_repository       # Read repository content
read_project          # Read project information
```

#### Optional Scopes (for enhanced features)
```
read_registry         # Read container registry
read_ci               # Read CI/CD pipelines
read_merge_request    # Read merge requests
```

5. Click **Create personal access token**
6. Copy the token immediately (shown only once)

### Step 2: Project Information

Gather this information from your GitLab project:

- **GitLab URL**: `https://gitlab.com` or your self-hosted URL
- **Project ID**: Found in project settings or URL
- **Project Path**: `group/project-name` format
- **Personal Access Token**: The token from Step 1

## Environment Configuration

Add these to your `.env` file:

```bash
# GitLab Integration
GITLAB_URL=https://gitlab.com
GITLAB_TOKEN=your-personal-access-token
GITLAB_PROJECT_ID=12345
GITLAB_PROJECT_PATH=your-group/your-project

# Optional: Default branch and settings
GITLAB_DEFAULT_BRANCH=main
```

## Configuration File

Add to your `config/config.yaml`:

```yaml
integrations:
  gitlab:
    enabled: true
    mock_mode: false
    
    # Project settings
    default_project_id: 12345
    default_branch: "main"
    
    # Merge request configuration
    merge_requests:
      states:
        - "opened"
        - "merged"
      max_results: 50
    
    # Issue configuration  
    issues:
      states:
        - "opened" 
        - "closed"
      max_results: 50
      labels:
        - "bug"
        - "enhancement"
        - "documentation"
```

## Features

### Merge Request Analysis

Analyze merge requests and code changes:

```slack
@BettySharp analyze merge request !123

@BettySharp review the changes in MR !456

@BettySharp what's the impact of merge request !789?
```

### Issue Tracking Integration

Work with GitLab issues:

```slack
@BettySharp analyze issue #123

@BettySharp show me recent bugs in the project

@BettySharp what tests should I write for issue #456?
```

### Pipeline and CI/CD Insights

Get insights about CI/CD pipelines:

```slack
@BettySharp analyze pipeline failures for MR !123

@BettySharp show me test results for the latest commit
```

## Project Configuration

### Single Project Setup

For a single project:

```yaml
integrations:
  gitlab:
    default_project_id: 12345
    default_project_path: "mygroup/myproject"
```

### Multiple Projects

For multiple projects:

```yaml
integrations:
  gitlab:
    projects:
      - id: 12345
        path: "frontend/web-app"
        name: "Web Application"
      - id: 67890
        path: "backend/api-service"  
        name: "API Service"
```

### Self-Hosted GitLab

For GitLab CE/EE self-hosted instances:

```bash
# Environment variables
GITLAB_URL=https://gitlab.yourcompany.com
GITLAB_TOKEN=your-token
```

```yaml
# Configuration
integrations:
  gitlab:
    base_url: "https://gitlab.yourcompany.com"
    api_version: "v4"
```

## Merge Request Integration

### Analysis Capabilities

Dev Agents can analyze:

- **Code changes** - Diff analysis and impact assessment
- **File modifications** - Which files changed and how
- **Commit history** - Individual commits in the MR
- **Comments and discussions** - Review feedback and conversations
- **Approval status** - Review approvals and requirements

### Automatic Linking

Link merge requests to commits:

```bash
# Commit messages that link to MRs
git commit -m "Fix authentication bug - see !123"
git commit -m "Implement user profile - closes !456"
```

## Issue Integration

### Issue Analysis

Analyze GitLab issues for:

- **Requirements understanding** - Break down issue descriptions
- **Testing recommendations** - What to test based on issue type
- **Implementation planning** - Development approach suggestions
- **Risk assessment** - Potential complications and considerations

### Issue Labels and Milestones

Configure relevant labels and milestones:

```yaml
integrations:
  gitlab:
    issues:
      relevant_labels:
        - "bug"
        - "enhancement"
        - "security"
        - "performance"
      track_milestones: true
```

## Testing and Validation

### Test Connection

Verify your GitLab integration:

```bash
python -c "
from src.integrations.gitlab.config import GitLabConfig
from src.core.config import BaseConfig

config = GitLabConfig(BaseConfig())
if config.is_configured():
    print('✓ GitLab configuration valid')
    print(f'URL: {config.get_base_url()}')
    print(f'Project: {config.get_project_id()}')
else:
    print('❌ Configuration incomplete')
"
```

### Mock Mode

For testing without GitLab access:

```yaml
integrations:
  gitlab:
    enabled: true
    mock_mode: true  # Uses mock data for testing
```

### API Testing

Test API connectivity:

```bash
# Test authentication
curl --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "$GITLAB_URL/api/v4/user"

# Test project access  
curl --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "$GITLAB_URL/api/v4/projects/$GITLAB_PROJECT_ID"
```

## Troubleshooting

### Common Issues

#### Authentication Failed

```bash
# Verify token is valid and hasn't expired
curl -I --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "$GITLAB_URL/api/v4/user"
```

#### Project Not Found

```bash
# Check project ID and permissions
curl --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "$GITLAB_URL/api/v4/projects/$GITLAB_PROJECT_ID"
```

#### Rate Limiting

GitLab has API rate limits. Configure requests appropriately:

```yaml
integrations:
  gitlab:
    api:
      rate_limit_delay: 1000  # milliseconds between requests
      max_retries: 3
```

### Debug Mode

Enable detailed logging:

```bash
export LOG_LEVEL=DEBUG
python -c "
from src.integrations.gitlab.client import GitLabClient
# Test operations with debug output
"
```

## Security Considerations

### Token Security

- **Environment variables** - Store tokens in `.env` file only
- **Minimal scopes** - Grant only necessary permissions
- **Regular rotation** - Update tokens periodically  
- **Expiration dates** - Set appropriate token expiration

### Data Privacy

Dev Agents accesses:
- ✅ Public project information
- ✅ Merge request metadata and diffs
- ✅ Issue descriptions and comments
- ✅ CI/CD pipeline results
- ❌ No modification of project data
- ❌ No access to sensitive files or secrets

## Best Practices

1. **Descriptive MRs** - Write clear merge request descriptions
2. **Consistent labeling** - Use consistent issue and MR labels
3. **Link commits** - Reference issues/MRs in commit messages
4. **Regular cleanup** - Close stale issues and merged branches
5. **Team coordination** - Ensure team understands the integration

## Advanced Configuration

### Custom Webhooks

For real-time updates, configure GitLab webhooks:

```yaml
integrations:
  gitlab:
    webhooks:
      enabled: true
      events:
        - "merge_requests"
        - "issues"
        - "push"
      endpoint: "https://your-devagents-instance.com/webhooks/gitlab"
```

### Branch-Specific Analysis

Configure branch-specific behavior:

```yaml
integrations:
  gitlab:
    branches:
      main:
        auto_analyze: true
        require_review: true
      develop:
        auto_analyze: true
        require_review: false
      feature/*:
        auto_analyze: false
```

## GitLab CI/CD Integration

### Pipeline Analysis

Analyze CI/CD pipeline results:

```slack
@BettySharp analyze failing tests in pipeline 12345

@BettySharp what's causing the deployment failures?

@BettySharp review test coverage for this MR
```

### Configuration Examples

Example `.gitlab-ci.yml` integration:

```yaml
# .gitlab-ci.yml
stages:
  - test
  - analyze
  - deploy

dev-agents-analysis:
  stage: analyze
  script:
    - curl -X POST "$DEV_AGENTS_WEBHOOK" \
        -H "Content-Type: application/json" \
        -d '{"pipeline_id": "$CI_PIPELINE_ID", "project_id": "$CI_PROJECT_ID"}'
  only:
    - merge_requests
```

## Next Steps

- Review [environment variables](../environment-variables.md) for additional options
- Configure [Git integration](git.md) for local repository analysis  
- Customize [prompts](../prompts-yaml.md) for GitLab-specific workflows
- Set up [Slack integration](slack.md) to receive GitLab insights in Slack

## API Reference

Dev Agents uses these GitLab APIs:

- **Projects API**: `https://docs.gitlab.com/ee/api/projects.html`
- **Merge Requests API**: `https://docs.gitlab.com/ee/api/merge_requests.html`
- **Issues API**: `https://docs.gitlab.com/ee/api/issues.html`
- **Pipelines API**: `https://docs.gitlab.com/ee/api/pipelines.html`