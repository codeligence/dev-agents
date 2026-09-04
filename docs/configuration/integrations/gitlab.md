# GitLab Integration

GitLab supplies **merge requests**, **issues** and **pipelines** to the agent. The code itself
still comes from the [local checkout](git.md).

## Create an access token

1. **User Settings → Access Tokens** (or a project/group token for narrower access).
2. Grant `read_api` — plus `read_repository` if you want the token to reach repository content.
3. Copy the token (`glpat-…`).

The project ID is on the project's overview page, right under the project name.

## Configuration

```bash
GITLAB_API_URL=https://gitlab.com/api/v4
GITLAB_PROJECT_ID=12345
GITLAB_TOKEN=glpat-...
GITLAB_MOCK=false
```

All three values are required; with any of them missing the provider is treated as unconfigured
and silently not offered to the agent. `GITLAB_MOCK=true` short-circuits that check and returns
canned data.

Self-hosted GitLab works the same way — point `GITLAB_API_URL` at your instance
(`https://gitlab.example.com/api/v4`).

The bundled `config.yaml` wires these into the `pullrequests`, `issues` and `pipelines` slots of
the `default` project. For per-project credentials, override the slot:

```yaml
projects:
  frontend:
    pullrequests:
      gitlab:
        api_url: "https://gitlab.example.com/api/v4"
        project_id: "42"
        token: "@jinja {{ env.get('GITLAB_TOKEN', '') }}"
        mock: false
    pipelines:
      gitlab:
        api_url: "https://gitlab.example.com/api/v4"
        project_id: "42"
        token: "@jinja {{ env.get('GITLAB_TOKEN', '') }}"
        mock: false
```

## Using it

Reference merge requests and issues by ID:

```
@DevAgents analyze MR 128
@DevAgents what is issue 512 about?
@DevAgents why did the last pipeline fail?
```

Merge requests are looked up by their project-scoped IID, the number you see in the GitLab UI.

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Provider not offered | One of the three values is empty; run `dev-agents -v` |
| `401 Unauthorized` | Token expired or revoked |
| `404` on a valid MR | Wrong `GITLAB_PROJECT_ID`, or the token has no access to that project |
| `429 Too Many Requests` | Instance rate limit — retry, or use a token with a higher limit |

## Notes

- `read_api` is enough for analysis; Dev Agents never writes to GitLab.
- Project and group tokens scope access to exactly one project or group, which is preferable to a
  personal token in shared deployments.

## Next steps

- [config.yaml](../config-yaml.md#providers)
- [Environment variables](../environment-variables.md#providers)
