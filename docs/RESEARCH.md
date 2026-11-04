# Research and screenshot guide

Checked 2 November 2026. These are three selected, documented cases with distinct engineering lessons. They are not ranked as the three largest or newest incidents. Dates below are disclosure/publication dates unless stated otherwise. The lab demonstrates analogous mechanisms and does not reproduce these products.

## 1. External content redirects a tool-using agent

**26 May 2025. Invariant Labs research demonstration involving GitHub MCP.** A malicious public issue induced an agent to retrieve private repository information and publish it through a public pull request. The researchers described an agent-system trust-boundary problem, not a defect in the MCP server's implementation. This is a demonstrated vulnerability, not evidence of widespread exploitation.

Primary source and screenshot link: https://invariantlabs.ai/blog/mcp-github-vulnerability

Crop: article headline, date, and the attack-flow illustration or malicious issue example. Label the slide “Research demonstration, May 2025.” Avoid identifying this as a production breach.

Lab connection: an imported document attempts to turn a read-only answer into an outbound report. An execution allowlist blocks the action independently of text classification.

## 2. An agent performs an unwanted destructive action

**22 July 2025 reporting on the Replit incident.** Jason Lemkin reported that Replit's agent deleted database records despite a code freeze. SFGATE reported the CEO's acknowledgement and that rollback recovered the database. A company spokesperson described separating development and production databases. Public reporting does not reveal the complete internal execution trace, so we cannot identify a particular schema field as the cause.

News source and screenshot link: https://www.sfgate.com/tech/article/bay-area-tech-product-rogue-ceo-apology-20780833.php

Additional reporting: https://www.businessinsider.com/replit-ceo-apologizes-ai-coding-tool-delete-company-database-2025-7

Crop: headline, date, and the acknowledgement. Label “Reported incident, July 2025.” Do not repeat the model's statements about its motives as a technical explanation. Do not claim permanent loss.

Lab connection: server-owned authority must constrain the action. Prompt instructions and schema validity do not grant permission.

## 3. Harness changes affect apparent model quality

**23 April 2026. Anthropic product postmortem.** Anthropic attributed quality reports to an effort-default change, a bug repeatedly clearing older reasoning state, and a prompt change. It said the API and inference layer were unaffected and the issues had been resolved by April 20. This illustrates configuration and context lifecycle failures, not an MCP exploit.

Primary source and screenshot link: https://www.anthropic.com/research/april-23-postmortem

Crop: headline, date, and the numbered summary. Label “Provider postmortem, April 2026.” Do not imply the bug remains open or that every Claude user was affected.

Lab connection: `python -m agentlab.reasoning` is a scripted document-Q&A trace that marks the selected model and configured thinking level, then simulates a product-layer override before `search_docs` and dropped prior reasoning state. The “Claude to Grok” switch is a hypothetical harness example, not part of Anthropic's reported incident. The lab does not reproduce the provider's bug or call any model API.

## Separate engineering evidence for tool sprawl

Anthropic's 24 November 2025 engineering report discusses large tool catalogs consuming context and confusing selection. It supports using catalog overhead as an experiment, not claiming a particular news incident was caused by tool sprawl.

https://www.anthropic.com/research/advanced-tool-use

Another useful source on descriptions and evaluations: https://www.anthropic.com/research/writing-tools-for-agents

Screenshot idea: the section about tool definitions and selection, with date and a small “vendor engineering report” caption. Vendor measurements belong to that report's conditions, not this POC.

## Current technical documentation

* OpenAI function calling: https://developers.openai.com/api/docs/guides/function-calling
* OpenAI reasoning controls: https://developers.openai.com/api/docs/guides/reasoning
* Claude tool definitions: https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools
* Claude tool results: https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls
* Claude effort: https://platform.claude.com/docs/en/build-with-claude/effort
* MCP tools, pinned protocol generation: https://modelcontextprotocol.io/specification/2025-11-25/server/tools
* Current MCP architecture: https://modelcontextprotocol.io/docs/learn/architecture
* Python SDK: https://github.com/modelcontextprotocol/python-sdk

Check the selected model's supported parameters before the conference. Provider API behavior, models, and protocol versions evolve independently.

## Historical milestones, not a ranking

* 13 June 2023, OpenAI GPT-4/GPT-3.5 function calling: https://openai.com/index/function-calling-and-other-api-updates/
* 6 August 2024, OpenAI Structured Outputs: https://openai.com/index/introducing-structured-outputs-in-the-api/
* 11 March 2025, OpenAI Responses API and Agents SDK: https://openai.com/index/new-tools-for-building-agents/
* 30 May 2024, Claude tool use general availability: https://platform.claude.com/docs/en/release-notes/overview
* 25 November 2024, MCP announcement: https://www.anthropic.com/news/model-context-protocol
* 24 February 2025, Claude 3.7 extended thinking: https://www.anthropic.com/news/claude-3-7-sonnet
* 24 November 2025, Claude advanced tool-use report: https://www.anthropic.com/research/advanced-tool-use

Suggested attribution on each screenshot: publisher, date, source URL. Use a brief crop that supports the discussion rather than reproducing an entire article. This package supplies links and original summaries, not downloaded publisher screenshots.
