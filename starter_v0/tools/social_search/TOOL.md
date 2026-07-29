---
name: social_search
track: core
kind: live_api
provider: Tavily Search (X/Twitter web-index fallback)
requires_env: [TAVILY_API_KEY]
inputs: [query, search_type, limit]
outputs: [items]
side_effect: false
---
# social_search

Searches public X/Twitter pages by keyword through Tavily's live web index.
`search_type=Latest` adds a recency constraint; `Top` ranks by Tavily relevance.
