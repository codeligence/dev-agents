# Azure DevOps Integration

Azure DevOps supplies **pull requests** and **work items** to the agent. The code itself still
comes from the [local checkout](git.md).

## Create a Personal Access Token

1. In Azure DevOps: **User settings → Personal access tokens → New Token**.
2. Scope it to the organization you want, pick an expiry, and grant **read** access to:
   **Code**, **Work Items**, **Pull Requests** (and **Build** if you want pipeline context).
3. Copy the token immediately — it is shown once.

You also need the organization name, the project name, and the repository ID (or name) from the
repository URL: `https://dev.azure.com/{organization}/{project}/_git/{repository}`.

## Configuration

```bash
AZURE_URL=https://dev.azure.com
AZURE_DEVOPS_ORGANIZATION=my-org
AZURE_DEVOPS_PROJECT=my-project
AZURE_DEVOPS_PAT=your-pat
AZURE_DEVOPS_REPOID=my-repo
AZURE_DEVOPS_MOCK=false
```

All five values are required; with any of them missing the provider is treated as unconfigured and
silently not offered to the agent. `AZURE_DEVOPS_MOCK=true` short-circuits that check and returns
canned data — useful for local development and tests.

The bundled `config.yaml` wires these into both the `pullrequests` and `issues` slots of the
`default` project. To use different credentials per project, override the slot in
`config/config.custom.yaml`:

```yaml
projects:
  backend:
    pullrequests:
      devops:
        url: "https://dev.azure.com"
        organization: "my-org"
        project: "backend"
        pat: "@jinja {{ env.get('AZURE_DEVOPS_PAT', '') }}"
        repoId: "backend-api"
        mock: false
```

## Using it

Reference pull requests and work items by ID:

```
@DevAgents analyze PR 4711
@DevAgents what does work item 1234 ask for?
@DevAgents summarize the changes in pull request 4711 for the release notes
```

The agent fetches the PR or work item, resolves the branches involved, and researches the diff in
the local checkout.

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Provider not offered | One of the five values is empty; run `dev-agents -v` and look for the config check |
| `401` / `403` | PAT expired, wrong organization, or missing read scope |
| PR or work item not found | The ID belongs to a different project, or `AZURE_DEVOPS_PROJECT` / `REPOID` point elsewhere |

## Notes

- Use a token with read-only scopes; Dev Agents never writes to Azure DevOps.
- Set an expiry and rotate the PAT; store it in a secret manager, not in a committed `.env`.

## Next steps

- [config.yaml](../config-yaml.md#providers)
- [Environment variables](../environment-variables.md#providers)
