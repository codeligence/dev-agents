# dev-agents

**An AI agent that lives in Slack and gives your whole team developer-like access to the codebase.**

Open source (MIT) · Self-hosted · Your data stays yours · Deploy in 5 minutes


![Build Status](https://img.shields.io/badge/build-pass-brightgreen.svg)
[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://pypi.org/project/dev-agents/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/codeligence/dev-agents/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code Quality](https://img.shields.io/badge/code%20quality-black%20%7C%20%20ruff%20%7C%20mypy%20%7C%20bandit-brightgreen.svg)](https://shields.io)

[Deploy Now](https://setup.dev-agents.ai){ .md-button .md-button--primary }
[Quick Start](quick-start.md){ .md-button }
                         
---

## What is dev-agents?

dev-agents is an AI teammate that connects to your code repositories and makes your codebase accessible to your entire team through Slack or Teams.

Your product owner asks how the authentication flow works. Support traces a customer bug to the relevant code. DevOps asks which services changed in the last sprint. A new hire asks how the deployment pipeline is set up. Nobody had to interrupt a developer — the agent answers from the actual code.

One agent, one core skill: code research. Your whole team talks to it where they already work.

## Get started

<div class="grid cards" markdown>

-   **Quick Start**

    ---

    Deploy dev-agents with Docker in 5 minutes.

    [Get started](quick-start.md)

-   **Configuration**

    ---

    Connect Slack, git providers, issue trackers, and AI models.

    [Configure](configuration/config-yaml.md)

-   **Setup Wizard**

    ---

    Generate your config interactively — no manual editing.

    [Launch wizard](https://setup.dev-agents.ai)

</div>

## Skills

| Skill | What it does | Availability |
|-------|-------------|--------------|
| **Code Research** | Answers questions about your codebase in plain English. Anyone on the team can ask. | Open source |
| **Test Plan Generation** | Generates test plans from pull requests — what to test, what might break, edge cases to cover. | [Hosted plans](https://codeligence.com) |
| **Release Notes** | Turns merged PRs into clear changelogs your product team can actually read. | [Hosted plans](https://codeligence.com) |
| **Code Review** | Reviews PRs for patterns, conventions, risk flags, and testing gaps. | [Hosted plans](https://codeligence.com) |
| **Story Refinement** | Improves user stories with concrete, testable acceptance criteria based on the actual code. | [Hosted plans](https://codeligence.com) |
| **Log Analysis** | Surfaces root causes from production logs, linked to relevant code and recent changes. | [Hosted plans](https://codeligence.com) |

## Integrations

| Category | Supported |
|----------|-----------|
| **Chat** | Slack, Teams |
| **Git providers** | GitHub, GitLab, Azure DevOps, Bitbucket |
| **Issue trackers** | Jira, GitHub Issues, GitLab Issues |
| **Logs** | ELK, Loki, log files |
| **LLM providers** | Anthropic, OpenAI, Google, Azure, local models |
| **Protocols** | MCP, AG-UI, A2A |

## Community

- [GitHub Issues](https://github.com/codeligence/dev-agents/issues)
- [GitHub Discussions](https://github.com/codeligence/dev-agents/discussions)
- [Security Policy](https://github.com/codeligence/dev-agents/security/policy)
