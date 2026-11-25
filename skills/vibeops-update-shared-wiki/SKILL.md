---
name: vibeops-update-shared-wiki
description: Publish shared knowledge changes from supplied PDF, DOCX, Markdown or accessible documents through the team's OpenWiki repository.
---

Use a separate working branch from the configured shared repository's latest publication branch. Keep search cache snapshots immutable. Read the authorized input using available document tools. Preserve PDF page numbers, Word headings or document links and versions. Verify OCR-sensitive tables and numbers against the original. If extraction is unavailable, report the missing evidence.

Locate existing sources under common, systems, databases or decisions inside sources/. Compare scope, effective dates and source authority. Update the matching topic or create one. Skip duplicates. Flag unresolved conflicts for review. Include only information approved for the shared audience.

Run OpenWiki initialization for a new wiki or update for an existing one from the Git root. Inspect generated sections against source facts, exceptions and citations. On failure report unpublished status. When authorized push a review branch and open a draft PR/MR containing source and generated changes. After merge verify the published commit with vibeops-search-wiki and a representative question.
