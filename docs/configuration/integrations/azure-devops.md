# Azure DevOps Integration

Connect Dev Agents with Azure DevOps to analyze work items, track changes, and provide development insights tied to your project management workflow.

## Azure DevOps Setup

### Step 1: Create Personal Access Token (PAT)

1. Go to your Azure DevOps organization
2. Click your profile icon → **Personal access tokens**
3. Click **+ New Token**
4. Configure the token:
   - **Name**: `Dev Agents Integration`
   - **Expiration**: Choose appropriate duration
   - **Scopes**: Select these permissions:

#### Required Scopes
```
Code (read)              # Read repositories and commits
Work Items (read)        # Read work items and queries
Project and Team (read)  # Read project information
Analytics (read)         # Read analytics data
```

#### Optional Scopes (for enhanced features)
```
Build (read)            # Read build information  
Release (read)          # Read release information
Test Management (read)  # Read test results
```

5. Click **Create** and copy the token immediately

### Step 2: Organization and Project Information

Gather this information from your Azure DevOps:

- **Organization URL**: `https://dev.azure.com/your-organization`
- **Project Name**: Your project name (visible in Azure DevOps)
- **Personal Access Token**: The token from Step 1

## Environment Configuration

Add these to your `.env` file:

```bash
# Azure DevOps Integration
AZURE_DEVOPS_URL=https://dev.azure.com/your-organization
AZURE_DEVOPS_TOKEN=your-personal-access-token
AZURE_DEVOPS_PROJECT=your-project-name

# Optional: Default work item configuration
AZURE_DEVOPS_DEFAULT_TEAM=your-team-name
```

## Configuration File

Add to your `config/config.yaml`:

```yaml
integrations:
  azure_devops:
    enabled: true
    mock_mode: false
    
    # Project settings
    default_project: "YourProject"
    default_team: "YourTeam"
    
    # Work item configuration
    work_item_types:
      - "User Story"
      - "Task" 
      - "Bug"
      - "Feature"
    
    # Query settings
    queries:
      max_results: 100
      default_fields:
        - "System.Id"
        - "System.Title"
        - "System.State"
        - "System.AssignedTo"
        - "System.CreatedDate"
        - "Microsoft.VSTS.Common.Priority"
```

## Features

### Work Item Analysis

Dev Agents can analyze work items and provide insights:

```slack
@BettySharp analyze work item 12345

@BettySharp what's the status of user story 98765?

@BettySharp show me recent changes for bug 54321
```

### Code-Work Item Correlation

Link code changes to work items:

```slack
@BettySharp analyze commits related to work item 12345

@BettySharp what code changes affect user story 98765?
```

### Testing Insights

Generate testing recommendations based on work items:

```slack
@BettySharp what tests should I write for work item 12345?

@BettySharp analyze test coverage for this sprint's work items
```

## Work Item Types

### Supported Types

Configure which work item types to analyze:

```yaml
integrations:
  azure_devops:
    work_item_types:
      - "User Story"       # Requirements and features
      - "Task"             # Development tasks
      - "Bug"              # Defects and issues
      - "Feature"          # Large features
      - "Epic"             # High-level initiatives
      - "Test Case"        # Test scenarios
```

### Custom Work Item Types

For custom work item types:

```yaml
integrations:
  azure_devops:
    work_item_types:
      - "User Story"
      - "Custom Feature"
      - "Technical Task"
    
    # Map custom types to standard analysis
    type_mappings:
      "Custom Feature": "Feature"
      "Technical Task": "Task"
```

## Query Configuration

### Default Queries

Dev Agents uses these default queries:

```wiql
# Active work items assigned to user
SELECT [System.Id], [System.Title], [System.State] 
FROM WorkItems 
WHERE [System.AssignedTo] = @Me 
  AND [System.State] <> 'Closed'

# Recent work items in current iteration  
SELECT [System.Id], [System.Title], [System.State]
FROM WorkItems
WHERE [System.IterationPath] = @CurrentIteration
  AND [System.ChangedDate] >= @Today - 7
```

### Custom Queries

Add custom queries in configuration:

```yaml
integrations:
  azure_devops:
    custom_queries:
      high_priority_bugs: |
        SELECT [System.Id], [System.Title] 
        FROM WorkItems 
        WHERE [System.WorkItemType] = 'Bug' 
          AND [Microsoft.VSTS.Common.Priority] <= 2
          AND [System.State] <> 'Closed'
      
      current_sprint_tasks: |
        SELECT [System.Id], [System.Title]
        FROM WorkItems
        WHERE [System.WorkItemType] = 'Task'
          AND [System.IterationPath] = @CurrentIteration
```

## Testing and Validation

### Test Connection

Verify your Azure DevOps integration:

```bash
python -c "
from src.integrations.azure.config import AzureDevOpsConfig
from src.core.config import BaseConfig

config = AzureDevOpsConfig(BaseConfig())
if config.is_configured():
    print('✓ Azure DevOps configuration valid')
    print(f'Organization: {config.get_organization()}')
    print(f'Project: {config.get_project()}')
else:
    print('❌ Configuration incomplete')
"
```

### Mock Mode

For testing without Azure DevOps access:

```yaml
integrations:
  azure_devops:
    enabled: true
    mock_mode: true  # Uses fake data for testing
```

## Troubleshooting

### Common Issues

#### Authentication Failed

```bash
# Verify token has correct permissions
curl -u :$AZURE_DEVOPS_TOKEN \
  https://dev.azure.com/your-org/_apis/projects?api-version=6.0
```

#### Project Not Found

```bash
# List available projects
curl -u :$AZURE_DEVOPS_TOKEN \
  https://dev.azure.com/your-org/_apis/projects?api-version=6.0
```

#### Work Item Access Denied

Check that your PAT has `Work Items (read)` permission and hasn't expired.

### Debug Mode

Enable detailed logging:

```bash
export LOG_LEVEL=DEBUG
python -c "
from src.integrations.azure.client import AzureDevOpsClient
# Test client operations with debug output
"
```

## Security Considerations

### Token Management

- **Secure storage** - Store PAT in environment variables only
- **Minimum permissions** - Grant only necessary scopes  
- **Regular rotation** - Rotate tokens periodically
- **Expiration monitoring** - Set appropriate expiration dates

### Data Access

Dev Agents accesses:
- ✅ Work item metadata and descriptions
- ✅ Project and team information  
- ✅ Query results
- ❌ No modification of work items
- ❌ No access to sensitive attachments

## Best Practices

1. **Descriptive work items** - Write clear titles and descriptions
2. **Consistent linking** - Link commits to work items via commit messages
3. **Regular updates** - Keep work item status current
4. **Team coordination** - Ensure team members understand the integration
5. **Permission review** - Regularly review and update PAT permissions

## Advanced Features

### Commit Linking

Link commits to work items using commit messages:

```bash
git commit -m "Fix login bug - resolves AB#12345"
git commit -m "Implement user profile - relates to AB#98765"
```

Dev Agents will understand these relationships for analysis.

### Sprint Analysis

Analyze entire sprints:

```slack
@BettySharp analyze current sprint progress

@BettySharp what's the risk assessment for sprint 42?

@BettySharp generate sprint retrospective insights
```

### Release Planning

Get insights for release planning:

```slack
@BettySharp analyze work items for next release

@BettySharp what's the testing impact of release 2.1?
```

## API Integration

For advanced users, Dev Agents uses these Azure DevOps APIs:

- **Work Items API**: `https://docs.microsoft.com/en-us/rest/api/azure/devops/wit/`
- **Git API**: `https://docs.microsoft.com/en-us/rest/api/azure/devops/git/`
- **Build API**: `https://docs.microsoft.com/en-us/rest/api/azure/devops/build/`

## Next Steps

- Configure [GitLab integration](gitlab.md) as an alternative
- Set up [Git repository integration](git.md)
- Customize [prompts](../prompts-yaml.md) for Azure DevOps workflows