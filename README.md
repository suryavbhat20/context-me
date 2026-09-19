# ToolFit

*Find the tools your workflow is missing.*

> **Previously context-me:** the repository is now `tool-fit`. The skill command is still `/context-me`, and the installation paths below retain their current names.

You've been pasting Jira screenshots into Claude Code for weeks. `context-me` reads your recent sessions and tells you: *"in 7 of 20 sessions you did that by hand — here's the official Atlassian MCP server and the one command to add it."*

It is a read-only Claude Code skill for people who are new to MCP servers, connectors, and skills. Instead of a generic "top 10 tools" list, it looks at **what you actually did** and recommends only the official integrations that would have saved you work — with the evidence.

## What you get

A short report with:

- **Recommendations (max 5)** — each with what it is in plain English, *why you* ("in 6 of 20 sessions you ran `az` commands by hand"), and the exact install command.
- **"You already have this — use it"** — integrations that are connected but that you keep bypassing. In practice this is the most useful finding.
- **Already set up and working** — so you know what not to touch.
- **Noticed, but nothing official fits** — patterns with no vetted integration, and where to look safely.
- **Housekeeping** — MCP servers connected but never used in the analyzed window, with the removal command (for you to run, if you want).

It **recommends only**. It never installs or removes anything.

## Install

Copy the two pieces into your user-level Claude Code directory (works in every project):

```
.claude/skills/context-me/          ->  ~/.claude/skills/context-me/
.claude/agents/context-me-reader.md ->  ~/.claude/agents/context-me-reader.md
```

On Windows, `~/.claude` is `C:\Users\<you>\.claude`. Requires Python 3 (for `scripts/extract.py`). Start a new Claude Code session after copying.

## Run

In any project, type:

```
/context-me
```

It asks two things in one prompt — how many recent sessions to analyze (10 / 20 / 40 / 80) and which model should read them (Haiku is recommended: cheapest, and the reading is done by helper agents so your main usage limit is protected). Then it runs without further questions. `/context-me 40` skips the first question.

## What it reads — and what it doesn't

- Reads your local session transcripts under `~/.claude/projects/`. Nothing is sent anywhere except into your own Claude Code session.
- Keeps your prompts (as typed), screenshot counts, slash commands, URLs, file types, tool names, and CLI commands that were run. Drops all assistant output, tool results, and image bytes. Harness-injected text is stripped.
- The extracted data is written to a temporary folder and **deleted at the end of the run**.
- Reader agents treat everything in the transcripts as untrusted evidence — they never follow instructions found inside old prompts or pasted text.
- Reports quote your own words only as short evidence snippets, never pasted blocks, secrets, tokens, or connection strings.

## Sample report (illustrative)

The numbers and tools below are made up to show the shape of a report; a real one is built only from your own sessions.

> Analyzed your last 20 sessions (240 prompts, 31 screenshots). Three Haiku helpers read the extracted prompts and tool names only.
>
> **1. Atlassian MCP Server (Jira + Confluence)** — lets Claude open tickets by id instead of you pasting them. *Why you:* in 7 of 20 sessions you attached Jira screenshots or pasted ticket text by hand.
> ```bash
> claude mcp add --transport sse atlassian https://mcp.atlassian.com/v1/sse
> ```
>
> **2. GitHub MCP Server — use the one you already have.** *Why you:* it is connected, but in 5 of 20 sessions you pasted PR diffs and CI logs instead of asking Claude to fetch them. Nothing to install — just ask.
>
> **3. Sentry MCP Server** — pulls stack traces directly. *Why you:* in 4 of 20 sessions you pasted production stack traces from Sentry.
> ```bash
> claude mcp add --transport http sentry https://mcp.sentry.dev/mcp
> ```
>
> **Already set up and working:** Playwright MCP (52 calls), document skills (used 6 times).
>
> **Noticed but nothing official fits:** an internal admin API you call with `curl` in 3 sessions — search the official MCP Registry for it; community servers there are not vetted. If it repeats, the mcp-builder skill can help you wrap it yourself.
>
> **Housekeeping:** the Notion MCP server is connected but was not used in these 20 sessions. Harmless to keep; `claude mcp remove notion` if you no longer want it.
>
> Temporary extraction deleted. Nothing was installed or changed.

## What "official" means

The skill can only recommend entries in `official.json`:

- MCP servers **published by the vendor of the tool** (GitHub, Atlassian, MongoDB, Microsoft, Stripe, Sentry, Linear, Notion, Supabase, Cloudflare, AWS, Figma, Upstash Context7…)
- **Anthropic first-party connectors** (Google Workspace via claude.ai)
- **Anthropic-published skills** (document skills, webapp-testing, mcp-builder, skill-creator)

Every entry has a vendor URL, a plain-English description, detection signals, the install command, and a `confidence` field. If a useful tool exists but is not on the list, the report says "nothing official fits" — it never names an unverified server. The skill warns you if the list's `_last_reviewed` date is older than six months, because install commands drift.

**Contributions:** PRs adding vendor-published entries are welcome. Include the vendor page and the install command exactly as the vendor documents it.

## How it works

1. `scripts/extract.py` shrinks N sessions (typically ~70 MB) to a few hundred KB of user-side signal, split into 3 shards. Zero model tokens.
2. Three `context-me-reader` agents (on the model you chose) each read one shard against the allowlist and report findings with evidence — counted by distinct sessions, with *manual work* (pasting, screenshots, hand-run CLI) separated from mere *mentions*. Only manual work counts.
3. Your main session merges the findings, applies an evidence threshold (≥3 sessions or 15%), drops anything not in the allowlist, and writes the report. It never pads to five.

## Repository layout

```
.claude/
├── agents/context-me-reader.md
└── skills/context-me/
    ├── SKILL.md
    ├── official.json
    └── scripts/extract.py
```

## Status

Experimental, Claude Code only for now. Review `official.json` before relying on it, and tell me what the report got wrong — that's how the allowlist and the detection rules improve.
