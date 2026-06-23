# Cofacts Knowledge Base

This repository is the institutional memory of [Cofacts](https://cofacts.tw) — a Taiwan-based open-source fact-checking platform. It stores raw meeting notes alongside a curated wiki maintained by AI agents and human contributors.

## Structure

```
src/meetings/YYYY/YYYYMMDD.md   # raw meeting notes (2017 – present)
wiki/                            # curated knowledge
  people/                        # contributors
  projects/                      # thematic initiatives
  activities/                    # recurring events (小聚, 大松)
  index.md
```

### Layer 1: `src/meetings/`

Over 500 meeting notes dating back to 2017, imported from [g0v HackMD](https://g0v.hackmd.io/@cofacts/meetings). Each file carries OKF frontmatter (`type`, `title`, `resource`, `tags`, `timestamp`) so it can be read by both humans and AI agents.

New meeting notes are added after each weekly meeting via the `/post-meeting-summarize` Claude Code skill.

### Layer 2: `wiki/`

Concept pages synthesised from meeting notes. Follows the [Open Knowledge Format (OKF) spec](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md). Pages are created when a topic recurs across three or more meetings, and are maintained by AI agents with human review.

| Directory | Type | Content |
|-----------|------|---------|
| `people/` | `Person` | Contributors — role, focus areas, active period |
| `projects/` | `Project` | Thematic initiatives (e.g. CCPRIP, 主機搬遷) |
| `activities/` | `Event` | Recurring events — venue, setup, retrospective notes |

## Workflow

```
Weekly meeting on HackMD
        │
        ▼  /post-meeting-summarize
src/meetings/YYYY/YYYYMMDD.md   ← committed to this repo
        │
        ▼  AI agent (wiki branch → PR → human approval)
wiki/**/*.md                     ← curated knowledge
```

## For AI Agents

See [AGENTS.md](AGENTS.md) and [CLAUDE.md](CLAUDE.md) for conventions, frontmatter schemas, and which skills write to which layer.

## Related

- [Cofacts website](https://cofacts.tw)
- [All meeting notes on HackMD](https://g0v.hackmd.io/@cofacts/meetings)
- [Cofacts GitHub org](https://github.com/cofacts)
