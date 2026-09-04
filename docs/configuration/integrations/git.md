# Git Integration

Dev Agents analyzes a **local clone** of your repository. Everything the code research tools do —
listing directories, reading files, grepping, diffing branches — runs against that checkout.

## Configuration

```bash
GIT_REPO_PATH=/path/to/your/repo
GIT_AUTOPULL=false
GIT_PULL_INTERVAL_SECONDS=120
```

Or per project in `config/config.custom.yaml`:

```yaml
projects:
  backend:
    git:
      path: "/code/backend"
      defaultBranch: "develop"
      autoPull: true
      pullIntervalSeconds: 300
```

| Key | Environment variable | Default | Description |
|-----|----------------------|---------|-------------|
| `path` | `GIT_REPO_PATH` | `/code` | Path to the checkout; falls back to the current directory when empty |
| `defaultBranch` | — | `main` | Branch used as the comparison base |
| `autoPull` | `GIT_AUTOPULL` | `false` | Run `git pull` before an analysis |
| `pullIntervalSeconds` | `GIT_PULL_INTERVAL_SECONDS` | `120` | Rate limit for auto-pull |

In Docker, mount the repository at the configured path:

```bash
docker run --rm -it --env-file=.env -v /path/to/your/repo:/code codeligence/dev-agents
```

## Requirements

- A real clone with a `.git` directory (not an export or a shallow archive).
- Read access for the user running Dev Agents.
- Full history where you want branch comparisons — a shallow clone limits diffs and `git log`.
- For `autoPull`: a remote the process can fetch from non-interactively (deploy key or token in
  the remote URL). Auto-pull failures are logged and never abort the request.

Multiple projects each point at their own checkout; the agent picks one via its project context.

## What the agent can do

Read-only git plumbing, run in the checkout:

- Diff two branches or refs (three-dot diff against the merge base), with per-file status and
  line counts
- Read commits between refs
- List the most recent tags
- Read files, list directories and grep at a given ref

Dev Agents never commits, pushes, or rewrites history. The only write operation is `git pull`,
and only when `autoPull` is enabled.

## Notes

- Files that reach the agent reach your LLM provider. Keep secrets out of the repository — a
  checked-in `.env` or private key is readable by the code research tools.
- Very large repositories work, but diffs across long ranges cost tokens; prefer narrow branch
  comparisons.

## Next steps

- [config.yaml](../config-yaml.md#projects) — project and provider slots
- [Azure DevOps](azure-devops.md), [GitLab](gitlab.md), [Linear](linear.md) — pull requests and
  issues on top of the checkout
