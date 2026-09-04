# Linear Integration

Linear supplies **issues** to the agent. It is configured in YAML only — unlike the other
providers, the bundled `config.yaml` ships no Linear block and no environment templates for it.

## Create an API key

1. In Linear: **Settings → API → Personal API keys → Create key**.
2. Copy the key (`lin_api_…`).

## Configuration

Add a `linear` entry to the `issues` slot of your project in `config/config.custom.yaml`:

```yaml
projects:
  default:
    issues:
      linear:
        api_key: "@jinja {{ env.get('LINEAR_API_KEY', '') }}"
        mock: false
```

```bash
LINEAR_API_KEY=lin_api_...
```

| Key | Required | Description |
|-----|----------|-------------|
| `api_key` | yes | Linear personal API key |
| `mock` | no | `true` returns canned data instead of calling the API (default `false`) |

The `@jinja` template is what makes `LINEAR_API_KEY` work — you can equally inline the key, but
keeping it in the environment is preferable. See
[config.yaml](../config-yaml.md#value-syntax) for the template syntax.

## Multiple issue trackers

A project can list several issue providers side by side; the agent picks the one that matches the
identifier it was given:

```yaml
projects:
  default:
    issues:
      linear:
        api_key: "@jinja {{ env.get('LINEAR_API_KEY', '') }}"
      jira:
        domain: "@jinja {{ this.providers.jira.domain }}"
        email: "@jinja {{ this.providers.jira.email }}"
        token: "@jinja {{ this.providers.jira.token }}"
```

## Using it

Reference issues by their Linear identifier:

```
@DevAgents what does ENG-1234 ask for?
@DevAgents summarize ENG-1234 and find the code it touches
```

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Provider not offered | The `issues.linear` block is missing, or `api_key` resolved to an empty string |
| Authentication error | Key revoked, or copied with surrounding whitespace |
| Issue not found | The key's user has no access to that team's issues |

## Notes

- Personal API keys inherit that user's permissions — create a dedicated integration user if you
  want to limit what the agent can read.
- Issue titles, descriptions and comments are sent to your LLM provider.

## Next steps

- [config.yaml](../config-yaml.md#projects)
- [Environment variables](../environment-variables.md)
