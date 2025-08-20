# Dev Agents

Welcome to Dev Agents! We devs love building software, but the reality in agile teams is that we spend more than half of our time with tasks _around_ the code: writing docs, reviewing PRs, communicating, researching, checking issues and logs, and so on. **Dev Agents** are here to reduce the painful stuff so we can focus on what matters most: **building cool software as a team**.

**Dev Agents** are self-hosted AI teammates that live in your tools and take over docs, reviews, release notes, triage, and more. It’s not just about freeing up **up to 10 hours per developer per week** - it’s about having a _companion_ that prepares work, lowers stress, and cuts the headaches around delivery.

We were tired of the closed-source solutions for dev team work assistants, so here we are. Coming from Java/C#, we love enterprise design patterns and clean code, so you will find quite a bit of it in this repo.

The project is open source (**AGPLv3**). An optional enterprise license and support (closed-source and managed deployments, customizations, SLAs) are offered by [Codeligence](mailto:sales@codeligence.com).

For CTOs: **multiply output without burning out your best engineers** - with auditability, predictable spend, and no SaaS lock-in.

## What you get (at a glance)

- **One Dev AI Avatar, many skills.** A consistent teammate (e.g. **Betty Sharp**, **Kira Draft**, **Nomi Stack**, **Vera Note**, **Luc Codewalker**) that shows up across your stack.

- **Open Source.** Free under **AGPLv3**; enterprise license available for closed-source use and support.

- **LLM-flexible.** Works with major hosted models or local LLMs; switch via config.

- **Built for real teams.** Especially 5+ dev orgs, multi-generation architectures, compliance/documentation needs.

- **Context and Integrations for Dev Teams.** While it works similarly to Claude Code or Gemini CLI, Dev Agents provide you with pre-engineered, dev specific contexts, prompts, and integrations for reproducible, cost-efficient results and a quick start.

**Concrete wins**

- Generate clean **release notes / change logs**
    
- **PR review** (human-style) and **PR guideline checking** (policy-style)
    
- **Root-cause** summaries from logs/issues
    
- **Test/impact notes** for QA & stakeholders
    
- **Support reply drafts** with evidence links
    
- **Migration assistance** across repos/services


## Quickstart (try it in 5 minutes)

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

## Interfaces & Integrations

**Interfaces (supported)**

- **Slack** • **Teams** • **AG-UI** • **MCP** • **CLI** • **A2A**
    

**Integrations (typical)**

- **Git providers:** GitHub / GitLab / Azure DevOps
    
- **Issues/PM:** Jira, GitHub Issues, GitLab Issues
    
- **Observability:** ELK / Loki / Files (others via MCP/tools)
    
- **Models:** All major providers and local LLMs

## Built-in agents 

    
|Skill|What Dev Agents Actually Delivers|Typical Ask|Time Saved|
|---|---|---|---|
|Release-Notes & Change-Log Builder _(implemented)_|Collates merged PRs → human-readable notes for communicating updates of libraries or products. Notes can be used to let an LLM check dependent implementations if they require updates.|`@DevAgents release notes for sprint 42`|1 h / release|
|Prod-Log Root-Cause Analysis _(porting)_|Reads ELK/Loki logs, surfaces likely cause + links to lines of code + suggests a solution.|`root-cause on error ID 2187`|30 min / incident|
|UI-Impact / Test-Note Generator _(implemented)_|Maps diff to UI views and flows and writes TODOs for testers.|`test notes for PR #557`|45 min / feature|
|Pull-Request Code Review & Guideline Checker _(implemented)_|Checks design patterns, best practices, technical debt, risk flags, and your commit/branch conventions.|on pull request|1 h / PR|
|Support-Ticket Drafts _(porting)_|Reads logs + context and drafts an issue reply.|`draft response for ticket #9123`|25 min / ticket|
|Code Migration Assistant _(porting)_|Suggests code changes when libs/frameworks jump; highlights cross-repo impacts.|`find all repos that use version X and check impact`|days → hours|
|User Story Writer _(implemented)_|Suggests user-story improvements and concrete details to add.|`"Add a feature to configure and print order reports"`|2 h / user story|

_We’re currently porting more use cases from our customer deployments._
