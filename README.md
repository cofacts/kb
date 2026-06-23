# Cofacts Knowledge Base

[Cofacts](https://cofacts.tw) is a Taiwan-based open-source fact-checking platform run by a civic volunteer community. This repository is Cofacts' institutional memory — weekly meeting notes dating back to 2017, plus a structured wiki distilled from them.

## I want to learn about Cofacts

- [Cofacts website](https://cofacts.tw) — the fact-checking database and LINE Bot
- [wiki/projects/](wiki/projects/) — background, goals, and evolution of key initiatives
- [wiki/people/](wiki/people/) — core contributors, their roles and focus areas
- [wiki/activities/](wiki/activities/) — how recurring events (小聚 meetups, 大松 hackathons) are run

## I want to look up past records

Meeting notes from 2017 onwards are stored by year under `src/meetings/`:

```
src/meetings/
  2017/
  2018/
  ...
  2026/YYYYMMDD.md
```

Each file has a `resource` field linking back to the original HackMD document. You can search across all notes on GitHub, or locally with:

```bash
git grep "keyword" src/meetings/
```

When a topic recurs across multiple meetings, `wiki/` will have a summary page that links back to the relevant meeting notes.

## Repository structure

```
src/meetings/YYYY/YYYYMMDD.md   # raw weekly meeting notes (2017 – present)
wiki/
  people/                        # contributors
  projects/                      # initiatives and workstreams
  activities/                    # recurring events
  index.md
```

`wiki/` content is distilled from meeting notes by an AI agent and merged after human review.

## Related links

- [Cofacts website](https://cofacts.tw)
- [Meeting notes on HackMD](https://g0v.hackmd.io/@cofacts/meetings)
- [Cofacts GitHub org](https://github.com/cofacts)

---

> Maintenance workflow and AI agent conventions: see [AGENTS.md](AGENTS.md) and [CLAUDE.md](CLAUDE.md)
