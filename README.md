<div align="center">
  <h1>dev-agents</h1>
  <p><b>An AI agent that lives in Slack and gives your whole team developer-like access to the codebase.</b></p>
  <p>Open source (MIT) &middot; Self-hosted &middot; Your data stays yours &middot; Deploy in 5 minutes</p>

  <br>

  <a href="https://setup.dev-agents.ai"><b>Deploy Now</b></a>
  &middot;
  <a href="#quick-start">Quick Start</a>
  &middot;
  <a href="https://docs.dev-agents.ai">Docs</a>
  &middot;
  <a href="https://dev-agents.ai">Website</a>
  <br><br>

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE.md)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/docker/pulls/codeligence/dev-agents)](https://hub.docker.com/r/codeligence/dev-agents)
![Build Status](https://img.shields.io/badge/build-pass-brightgreen.svg)
[![Code Quality](https://img.shields.io/badge/code%20quality-black%20%7C%20%20ruff%20%7C%20mypy%20%7C%20bandit-brightgreen.svg)](https://shields.io)

</div>

---

Your developers use Copilot to write code. But what about everyone else on the team?

Product owners need to understand what changed. QA needs test plans from pull requests. Support needs to trace bugs back to code. DevOps needs to analyze incidents. They all end up interrupting developers or waiting.

**dev-agents** connects to your repos, issue trackers, and logs, and makes all of it accessible through Slack. Anyone on the team can ask questions in plain English. No IDE required. No code skills needed.

> "What used to take days now happens automatically."
> — **CTO at a 50-user medical SaaS company** using dev-agents daily across engineering, product, and support teams

## What it does

Your team asks questions about the codebase in Slack — in plain English. No IDE, no git clone, no code skills needed.

```
@DevAgents how does the authentication flow work?
@DevAgents what changed in the payment module this sprint?
@DevAgents which files handle the webhook retry logic?
@DevAgents what's the difference between OrderService and OrderProcessor?
```

Code research is the core skill: anyone on the team can ask about architecture, recent changes, dependencies, or how a feature works and get an answer grounded in the actual code, not stale docs.

Hosted plans at [codeligence.com](https://codeligence.com) add maintained skills for test plans, release notes, code review, story refinement, and log analysis.

## Quick start

### Option 1: Docker (recommended)

```bash
# 1. Download config
wget -O .env https://raw.githubusercontent.com/codeligence/dev-agents/main/.env.example

# 2. Edit .env — add your Slack token, git provider, and LLM API key

# 3. Run (mount your cloned repo into the container)
docker run --rm -it --env-file=.env \
  -v /path/to/your/repo:/code \
  codeligence/dev-agents
```

Or use the **[Setup Wizard](https://setup.dev-agents.ai)** to generate your config interactively.

### Option 2: From source

```bash
git clone https://github.com/codeligence/dev-agents.git
cd dev-agents
cp .env.example .env    # then edit .env
pip install -e .[all]
python -m entrypoints.main
```

Then in Slack:

```
@DevAgents how does the authentication flow work?
```

## Why teams choose dev-agents

**Your infrastructure, your data.** Runs in your cloud or on-prem. No data leaves your environment. You bring your own LLM API keys. Your code and your team's questions stay on your infrastructure.

**Works where your team already works.** Slack and Teams. No new tool to adopt. No IDE needed. Your QA lead, product owner, and support team can use it on day one.

**Open source (MIT).** Full source code on GitHub. Your security team can audit everything. No copyleft restrictions, no procurement delays. Use it however you want.

**Any LLM provider.** Anthropic, OpenAI, Google, Azure, or run local models. Switch providers anytime without changing workflows.

**Multi-repo.** Connects to multiple repositories at once. Ask questions that span your entire codebase.

**Extensible.** Add custom skills for your team's specific workflows. Build on what's there or create something new.

## Integrations

| Category | Supported                               |
|----------|-----------------------------------------|
| **Chat** | Slack, Teams                            |
| **Git providers** | GitHub, GitLab, Azure DevOps, Bitbucket |
| **Issue trackers** | Jira, GitHub Issues, GitLab Issues      |
| **Logs** | ELK, Loki, log files                    |
| **LLM providers** | All major providerers + local models    |
| **Protocols** | MCP, AG-UI, A2A                         |

## Who it's for

**The whole team** — not just developers.

- **QA leads** tired of spending hours writing test plans from pull requests
- **Product owners** who need code-level answers but can't read code
- **Support engineers** tracing customer bugs without knowing the codebase
- **DevOps teams** analyzing incidents and deployment failures
- **Engineering managers** who need visibility without interrupting developers
- **CTOs** looking to give the whole team self-service access to project knowledge

Works best with teams of 10-200 on active, evolving codebases where documentation, testing, and cross-team communication matter.

## Self-hosted by design

Most AI dev tools are SaaS. Your code goes to their servers. Your questions go through their infrastructure.

dev-agents deploys to **your cloud** - AWS, Azure, GCP - or on-prem. You own the infrastructure. You control the data. You bring your own LLM keys and pay providers directly. No per-seat pricing surprises.

If your team already self-hosts GitLab, Jira, or other dev tools, you already believe in owning your infrastructure. This is the same philosophy applied to AI.

## Commercial support

Need an admin dashboard, team analytics, SSO, or dedicated support? See [codeligence.com](https://codeligence.com) for plans starting at $59/month — or [book a demo](https://calendar.codeligence.com).

## Community

- **Docs**: [docs.dev-agents.ai](https://docs.dev-agents.ai)
- **Issues**: [GitHub Issues](https://github.com/codeligence/dev-agents/issues)
- **Discussions**: [GitHub Discussions](https://github.com/codeligence/dev-agents/discussions)
- **Security**: [Security Policy](https://github.com/codeligence/dev-agents/security/policy)

## License

[MIT](LICENSE.md). Use it, fork it, deploy it, sell it. No restrictions.
