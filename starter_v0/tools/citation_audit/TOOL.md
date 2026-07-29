---
name: citation_audit
track: team
kind: local
provider: local deterministic validation
requires_env: []
inputs: [items, require_summary, deduplicate]
outputs: [items, rejected_items, issues, valid_count, rejected_count, all_cited]
side_effect: false
---
# citation_audit

Validates research items before they are passed to `format`. It rejects missing
or invalid URLs, missing titles, optionally missing summaries, and duplicate
URLs. A missing source name is inferred from a valid URL when possible.

Use this tool only after research or source-reading results already exist. It
does not search the web, read URLs, fact-check claims, or format the digest.
