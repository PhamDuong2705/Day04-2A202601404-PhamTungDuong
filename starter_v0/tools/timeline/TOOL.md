---
name: timeline
track: core
kind: live_api
provider: Tavily Search (X/Twitter web-index fallback)
requires_env: [TAVILY_API_KEY]
inputs: [screenname, limit]
outputs: [items]
side_effect: false
---
# timeline

Fetches recent posts from a single account. `screenname` is an account handle
without `@`. The implementation searches Tavily's live web index, constrained
to public `x.com` and `twitter.com` results.
