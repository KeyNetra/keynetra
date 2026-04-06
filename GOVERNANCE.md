# Governance

## Maintainers
- Core maintainers are responsible for release management, security triage, and architectural direction.
- Repository write access is restricted to maintainers and trusted release engineers.

## Decision Process
- API and schema changes require a documented rationale in pull requests.
- Breaking changes require a deprecation window and changelog migration notes.
- Security-sensitive changes require at least one maintainer security review.

## Release Cadence
- Patch releases: weekly or as needed for security/bug fixes.
- Minor releases: every 4-6 weeks.
- Emergency security releases: out-of-band.

## Contribution Workflow
- Fork + pull request workflow.
- CI must be green (tests, lint, typing, security scans, contract checks).
- At least one maintainer approval required before merge.
