---
name: vibeops-search-shared-knowledge
description: Find cited team knowledge such as shared API contracts, database notes, terminology and decisions in the configured Git knowledge repository.
---

1. Use the shared wiki root, commit and status supplied by the orchestrator handoff. If missing, report shared knowledge unavailable. Never synchronize during search.
2. Search only that root's openwiki/ Markdown. Read the index and up to three relevant sections initially.
3. Cite the Markdown path, heading and commit. Disclose stale-unverified when the remote was unreachable. Use the same snapshot throughout the session.
