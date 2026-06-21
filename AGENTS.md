# Cofacts KB — Agent Guide

## Structure

```
src/meetings/YYYY/YYYYMMDD.md   # Layer 1: raw meeting notes (read-only for wiki agents)
wiki/                            # Layer 2: curated knowledge (agent-maintained)
  decisions/
  projects/
  people/
  index.md
```

## Layer 1: src/meetings/

OKF frontmatter on every file:

```yaml
type: Meeting
title: "YYYYMMDD 會議記錄"
resource: "https://g0v.hackmd.io/@mrorz/NOTE_ID"
tags: [cofacts, meeting]
timestamp: "YYYY-MM-DDT20:00:00+08:00"
```

Skills that write here: `/post-meeting-summarize`

## Layer 2: wiki/

Agent-maintained concept pages. OKF frontmatter:

```yaml
type: Decision | Project | Person   # pick one
title: "..."
description: "..."                  # one sentence
tags: [cofacts, ...]
timestamp: "YYYY-MM-DDT..."         # update when editing
```

| Type | Use for |
|------|---------|
| `Decision` | Key decisions: what, when, why, current status |
| `Project` | Long-running initiatives: scope, progress, outcome |
| `Person` | Contributors: role, focus areas, active period |

**Conventions:**
- Cite raw sources as links: `[20210120](../src/meetings/2021/20210120.md)`
- Create a page when a topic spans ≥ 3 meetings
- `index.md` per directory — no frontmatter (list of links only)
