# Documentation Resources

KeyNetra docs share a unified visual identity. The same `data/imgs/logo.png` graphic anchors:

- `README.md` hero banner
- `docs/README.md` header overview
- Every quickstart/reference guide that embeds the logo via `<img src="/data/imgs/logo.png"...>`

Use this file as the entry point for doc sources, templates, and branding assets.

## Branding asset

- File: `data/imgs/logo.png`
- Use: hero banner, doc headers, quickstart references
- Recommended alt text: "KeyNetra Logo"

## Doc sources

- `README.md`: top-level landing
- `docs/api-endpoints.md`: HTTP contract details
- `docs/models/`: authorization model explanations
- `docs/policies.md`: policy structure guidance
- `docs/use-cases.md`: real-world example scenarios
- `docs/deep-dive/`: developer manual, code walkthrough, integration cookbook

Each markdown includes the same logo to keep visual continuity.

## When adding new docs

1. Save art in `data/imgs/` and reference via relative path `data/imgs/logo.png`.
2. Reuse the same hero markup `<p align="center"><img src="data/imgs/logo.png" alt="KeyNetra Logo" width="220"/></p>` for brand consistency.
3. Keep doc resources structured under `docs/` so the documentation site can render them uniformly.
