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
  <a href="#use-cases">Use Cases</a>
  ·
  <a href="#license">License</a>
  <br><br>

![Build Status](https://img.shields.io/badge/build-pass-brightgreen.svg)
[![Version](https://img.shields.io/badge/version-0.10.0-blue.svg)](https://pypi.org/project/dev-agents/)
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
* **Fast setup** – guided onboarding at **[setup.dev-agents.ai](https://setup.dev-agents.ai)**; run locally or on your server.
* **Built for teams** – shines with **5+ devs** and complex, evolving codebases where docs, compliance & handovers matter.
* **Context and Integrations for Dev Teams.** While it works similarly to Claude Code or Gemini CLI, Dev Agents provide you with pre-engineered, dev specific contexts, prompts, and integrations for reproducible, cost-efficient results and a quick start.

## Quick start

### Option 1: **Docker**

   **I. Get and edit configuration:**
   * Run the Setup Wizard: [https://setup.dev-agents.ai](https://setup.dev-agents.ai) to create a configuration for your setup.
   * Alternatively, download example configuration:
     ```bash
     wget -O .env https://raw.githubusercontent.com/codeligence/dev-agents/refs/heads/main/.env.example
     ```
   * For LLM config, see also [https://ai.pydantic.dev/api/models/base/](https://ai.pydantic.dev/api/models/base/) for supported models.

   **II. Mount repository and start container:**
   * Your repository needs to be already cloned locally.
     ```bash
     # Mount cloned repository and configuration
     docker run --rm -it --env-file=.env -v your/local/repo/path:/code codeligence/dev-agents
     ```
     
     Add `-v` argument to see verbose logs.

### Option 2: **Clone and run** (requires Python 3.11+):

   **I. Clone Dev Agents:**
   * Clone the repository:
      ```bash
      git clone https://github.com/codeligence/dev-agents.git
      cd dev-agents
      ```

   **II. Get and edit configuration:**
   * Run the Setup Wizard: [https://setup.dev-agents.ai](https://setup.dev-agents.ai)
   * Or use example .env:
      ```bash
      cp .env.example .env
      ```
   * Fill in credentials for your version control provider (Gitlab/Github), LLM provider (Anthropic/OpenAI), and optional integrations (Jira/DevOps)
   * Choose LLM model (OpenAI/Anthropic) - see [https://ai.pydantic.dev/api/models/base/](https://ai.pydantic.dev/api/models/base/) for supported models

   **III. Install dependencies and run Dev Agents**

      ```bash
      pip install -e .[all]     
      python -m entrypoints.main
      ```

Then interact in your tools (e.g. Slack):
`@DevAgents release notes for pull request 123 please`

## Use Cases

* **Release Notes & Changelog** – turns merged PRs into clear notes for products/libs.
* **PR Review & Compliance Check** – design patterns, conventions, risk flags.
* **Test-Notes** – maps diffs to flows; creates actionable test notes.
* **User Story Refining** – improves stories with concrete, testable detail.

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
