<div align="center">
  <h1>Codeligence Dev Agents</h1>
  <b>You have your copilot, but what about the agile team work outside the IDE? Dev Agents handle the nasty grind outside your IDE: docs, reviews, debugging, logs & delivery, so you peacefully focus on building.</b>
  
  <a href="https://setup.codeligence.com"><b>Setup Wizard</b></a>
  ·
  <a href="#quick-start">Quick start</a>
  ·
  <a href="#included-agents">Included agents</a>
  ·
  <a href="#license">License</a>
  <br><br>
</div>


**Core idea:** one consistent, named AI teammate (e.g. “Betty Sharp”) embedded into Slack, GitHub, DevOps, Jira & more—automating tedious, repeatable tasks around your codebase.

Build using the elegant [Pydantic AI](https://ai.pydantic.dev/) framework.

## Why use Dev Agents

* **Dev AI Avatar** – one persona, many skills; shows up across your stack with a single voice.
* **Open-source** – free under **AGPLv3**; commercial license available for closed-source deployments & enterprise support.
* **LLM-flexible** – works with major hosted or local models.
* **Ready now** – 4 production agents live; more being ported from customer projects.
* **Easily Customizable** – Easily add more use cases or customizations by extending base classes and implementing protocols.
* **Fast setup** – guided onboarding at **setup.codeligence.com**; run locally or on your server.
* **Built for teams** – shines with **5+ devs** and complex, evolving codebases where docs, compliance & handovers matter.
* **Context and Integrations for Dev Teams.** While it works similarly to Claude Code or Gemini CLI, Dev Agents provide you with pre-engineered, dev specific contexts, prompts, and integrations for reproducible, cost-efficient results and a quick start.

## Quick start

1. Option 1: **Run the Setup Wizard:** [https://setup.dev-agents.ai](https://setup.dev-agents.ai)
   Generates your config and start instructions for local or server deployment.
2. Option 2: **Clone and run** (example):

```bash
# 1) Clone
git clone https://github.com/codeligence/dev-agents.git
cd dev-agents

# 2) Copy example env and edit
cp .env.example .env

# 3) See src/entrypoints for possible interfaces. Start with command line, try Slack or AG-UI next
pip install -e .[all]
python -m entrypoints.cli_chat

# or use docker (coming soon)
```

Then interact in your tools (e.g. Slack):
`@BettySharp release notes for sprint 42`

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
