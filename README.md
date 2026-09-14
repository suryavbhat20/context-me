# context-me

`context-me` is a read-only Claude Code skill that examines extracted session
signals and identifies evidence-backed opportunities to use official MCP
servers, connectors, and skills.

## What it does

- Extracts compact signals from Claude Code sessions while preserving useful
  evidence.
- Runs parallel readers against an explicit official allowlist.
- Separates missing integrations, underused integrations, existing usage, and
  patterns that do not map to an approved product.
- Avoids inventing recommendations and excludes secrets from reports.

## Installation

Copy `.claude/skills/context-me` into your Claude Code skills directory and
`.claude/agents/context-me-reader.md` into your agents directory. The skill
expects Python 3 for `scripts/extract.py`.

## Repository layout

```text
.claude/
├── agents/context-me-reader.md
└── skills/context-me/
    ├── SKILL.md
    ├── official.json
    └── scripts/extract.py
```

This project is experimental. Review the allowlist and sanitize any exported
session data before sharing it.

