<div align="center">
  <h1>Codeligence Dev Agents</h1>
  <p><b>You have your copilot, but what about the agile team work outside the IDE? Dev Agents handle the nasty grind outside your IDE: docs, reviews, debugging, logs & delivery, so you peacefully focus on building.</b></p>
  
  <br>

  <a href="https://setup.dev-agents.ai"><b>Setup Wizard</b></a>
  ·
  <a href="#quick-start">Quick start</a>
  ·
  <a href="https://docs.dev-agents.ai">Docs</a>
  ·
  <a href="#included-agents">Included agents</a>
  ·
  <a href="#license">License</a>
  <br><br>

![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)
[![Version](https://img.shields.io/badge/version-0.9.2-blue.svg)](https://pypi.org/project/dev-agents/)
[![License](https://img.shields.io/badge/license-AGPL--3.0-blue.svg)](https://github.com/codeligence/dev-agents/blob/main/LICENSE.md)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code Quality](https://img.shields.io/badge/code%20quality-black%20%7C%20%20ruff%20%7C%20mypy%20%7C%20bandit-brightgreen.svg)](https://shields.io)

</div>


**Core idea:** one consistent, named AI teammate (e.g. “Betty Sharp”) embedded into Slack, GitHub, DevOps, Jira, Console & more - automating tedious, repeatable tasks around your codebase.

Build using the elegant [Pydantic AI](https://ai.pydantic.dev/) framework.

## Why use Dev Agents

* **Dev AI Avatar** – one persona, many skills; shows up across your stack with a single voice.
* **Open-source** – free under **AGPLv3**; commercial license available for closed-source deployments & enterprise support.
* **LLM-flexible** – works with major hosted or local models.
* **Ready now** – 4 production agents live; more being ported from customer projects.
* **Easily Customizable** – Easily add more use cases or customizations by extending base classes and implementing protocols.
* **Fast setup** – guided onboarding at **[setup.dev-agents.ai](setup.dev-agents.ai)**; run locally or on your server.
* **Built for teams** – shines with **5+ devs** and complex, evolving codebases where docs, compliance & handovers matter.
* **Context and Integrations for Dev Teams.** While it works similarly to Claude Code or Gemini CLI, Dev Agents provide you with pre-engineered, dev specific contexts, prompts, and integrations for reproducible, cost-efficient results and a quick start.

## Quick start

1. Option: **Run the Setup Wizard:** [https://setup.dev-agents.ai](https://setup.dev-agents.ai)
   Generates your config and start instructions for local or server deployment.
2. Option: **Use Docker**:

```bash
# 1) Get example env and edit
wget -O .env https://raw.githubusercontent.com/codeligence/dev-agents/refs/heads/main/.env.example

# 2) Run the CLI Chat in the docker container
docker run --rm -it --env-file=.env -v ./your-cloned-git-repo:/code codeligence/dev-agents
```

You need to mount your cloned Git repository into the container so that Dev Agents can work with the code.

6. Option: **Clone and run**:

```bash
# 1) Clone
git clone https://github.com/codeligence/dev-agents.git
cd dev-agents

# 2) Copy example env and edit
cp .env.example .env

# 3) See src/entrypoints for possible interfaces. Start with command line, try Slack or AG-UI next
pip install -e .[all]
python -m entrypoints.cli_chat
```

Then interact in your tools (e.g. Slack):
`@DevAgents release notes for pull request 123 please`

## Included agents

* **Release Notes & Changelog** – turns merged PRs into clear notes for products/libs.
* **PR Review & Guideline Checker** – design patterns, conventions, risk flags.
* **UI Impact / Test-Notes** – maps diffs to flows; creates actionable test notes.
* **User Story Writer** – improves stories with concrete, testable detail.

_We’re currently porting more use cases from our customer deployments:_

* **Prod Log Root-Cause Analysis** – surfaces likely cause, links to code, suggests fixes.
* **Support Reply Drafts** – proposes informed responses from logs/context.
* **Code Migration Assistant** – highlights cross-repo impacts for framework/library jumps.

## Who it’s for

* Engineering teams **5+ devs** on long-lived, multi-gen codebases
* Teams with **documentation/compliance/support** overhead
* CTOs who want to **multiply output** while protecting developer focus

## Interfaces & Integrations

**Interfaces**

- **Slack** • **Teams** • **AG-UI** • **MCP** • **CLI** • **A2A**
- Add more easily
    
**Integrations**

- **Git providers:** GitHub / GitLab / Azure DevOps
- **Issues/PM:** Jira, GitHub Issues, GitLab Issues
- **Observability:** ELK / Loki / Files (others via MCP/tools)
- **Models:** All major providers and local LLMs
- Add more easily

## License

Core is **AGPLv3** (free). Commercial license available for closed-source deployments, enterprise support, onboarding, and SLAs.

Contact [Codeligence Sales](mailto:sales@codeligence.com) for more info.
