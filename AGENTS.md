# Cofacts KB — Agent Guide

## Structure

```
src/meetings/YYYY/YYYYMMDD.md   # Layer 1: raw meeting notes (read-only for wiki agents)
wiki/                            # Layer 2: curated knowledge (agent-maintained)
  people/
  projects/
  activities/
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

Agent-maintained concept pages. Follows [OKF spec](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md). Frontmatter:

```yaml
type: Person | Project | Event   # pick one
title: "..."
description: "..."               # one sentence
tags: [cofacts, ...]
timestamp: "YYYY-MM-DDT..."      # update when editing
```

| Type | Directory | Use for |
|------|-----------|---------|
| `Person` | `people/` | Contributors: role, focus areas, active period |
| `Project` | `projects/` | Thematic initiatives (e.g. CCPRIP, 主機搬遷) — NOT GitHub repos |
| `Event` | `activities/` | Recurring events (小聚, 大松): venue info, setup layouts, insights from 檢討 |

**Conventions:**
- Cite raw sources as links: `[20210120](../src/meetings/2021/20210120.md)`
- Create a page when a topic spans ≥ 3 meetings
- `index.md` per directory — no frontmatter (list of links only)
