# Git Integration

Dev Agents requires access to your git repository to analyze code changes, understand project structure, and provide meaningful insights.

## Repository Setup

### Prerequisites

1. **Git repository** - Your project must be a git repository
2. **File permissions** - Dev Agents needs read access to the repository
3. **Clean working directory** - Uncommitted changes may affect analysis

### Configuration

#### Method 1: Environment Variable

Set the repository path using an environment variable:

```bash
# In your .env file
GIT_REPO_PATH=/path/to/your/repository
```

#### Method 2: config.yaml

Configure in your `config/config.yaml`:

```yaml
integrations:
  git:
    repository:
      path: "/path/to/your/repository"
```

### Automatic Path Resolution

If no path is specified, Dev Agents will attempt to find the git repository:

1. Check current working directory
2. Search parent directories for `.git` folder
3. Use the first valid git repository found

## Repository Requirements

### Git History

Dev Agents works best with repositories that have:

- **Commit history** - At least a few commits for context
- **Branch structure** - Clear branching strategy (main/develop)
- **Meaningful commit messages** - Descriptive commit messages help analysis

### File Structure

Optimize your repository for Dev Agents:

```
your-repo/
├── .git/                    # Git metadata
├── src/                     # Source code
├── tests/                   # Test files  
├── docs/                    # Documentation
├── README.md               # Project overview
├── .gitignore              # Git ignore rules
└── requirements.txt        # Dependencies (Python)
```

### Recommended .gitignore

Exclude files that don't need analysis:

```gitignore
# Dev Agents specific
.env
*.log

# Build artifacts
build/
dist/
*.egg-info/

# IDE files
.vscode/
.idea/
*.swp

# OS files
.DS_Store
Thumbs.db

# Language-specific
__pycache__/
node_modules/
.pytest_cache/
```

## Analysis Configuration

### File Size Limits

Configure maximum file sizes for analysis:

```yaml
integrations:
  git:
    analysis:
      max_file_size: 1048576  # 1MB in bytes
      exclude_patterns:
        - "*.log"
        - "*.bin"
        - "node_modules/*"
        - ".git/*"
        - "__pycache__/*"
```

### File Type Support

Dev Agents analyzes these file types:

- **Source code**: `.py`, `.js`, `.ts`, `.java`, `.go`, `.rust`, etc.
- **Configuration**: `.yaml`, `.json`, `.toml`, `.ini`
- **Documentation**: `.md`, `.rst`, `.txt`
- **Web**: `.html`, `.css`, `.scss`

## Repository Operations

### Read Operations

Dev Agents performs these read-only operations:

- **File reading** - Analyze source code content
- **Git log** - Review commit history and messages
- **Git diff** - Compare changes between commits/branches
- **Branch analysis** - Understand branching structure
- **File tree** - Navigate project structure

### No Write Operations

Dev Agents **never** modifies your repository:

- ❌ No commits
- ❌ No branch creation
- ❌ No file modifications
- ❌ No git operations that change state

## Troubleshooting

### Common Issues

#### Permission Denied
```bash
# Ensure read permissions
chmod -R +r /path/to/your/repository
```

#### Repository Not Found
```bash
# Verify path exists and contains .git
ls -la /path/to/your/repository/.git
```

#### Large Repository Performance
```yaml
# Increase exclusion patterns
integrations:
  git:
    analysis:
      exclude_patterns:
        - "vendor/*"
        - "third_party/*"
        - "*.min.js"
        - "*.bundle.*"
```

### Validation

Test your git integration:

```bash
python -c "
from src.integrations.git.git_repository import GitRepository
repo = GitRepository()
print('✓ Git repository accessible')
print(f'Repository path: {repo.repo_path}')
"
```

## Security Considerations

### Repository Access

- **Read-only access** - Dev Agents only reads, never writes
- **Local repositories** - No remote repository access required
- **Sensitive files** - Use `.gitignore` to exclude sensitive content
- **File permissions** - Maintain appropriate file system permissions

### Sensitive Data

Ensure sensitive information is not analyzed:

```gitignore
# Sensitive configuration
.env
secrets/
private_keys/

# Database files
*.db
*.sqlite

# Credential files
credentials.json
auth_keys.yml
```

## Best Practices

1. **Clean repository** - Keep your repository organized and clean
2. **Meaningful commits** - Write descriptive commit messages
3. **Regular branches** - Use consistent branching strategies
4. **Documentation** - Include README and inline documentation
5. **Ignore patterns** - Exclude unnecessary files from analysis

## Next Steps

- Configure [Slack integration](slack.md)
- Set up [Azure DevOps integration](azure-devops.md)
- Review [environment variables](../environment-variables.md)