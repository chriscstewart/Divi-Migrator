# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/).

> **Note:** This project is EXPERIMENTAL / "vibe coded" — use at your own risk.
> Always run `audit-init` + `migrate --dry-run` and verify output before any
> destructive step.

## [0.1.4] - 2026-08-13

### Added
- **Offline end-to-end simulation** (`divi-migrate simulate`, also `make
  simulate`). Boots an in-memory WordPress + DiviOps harness and runs the FULL
  migration pipeline (convert → validate → schema check → create draft → verify
  → publish → rename original) with **no live site**. Prints an integrity
  scorecard (drafts created, schema-valid drafts, originals renamed to `-old`,
  originals force-deleted = 0). This is the recommended smoke test and contributor
  demo — exercise the code start-to-finish without touching any real content.
- **Injectable clients on `MigrationOrchestrator`.** `wp` / `diviops` / `audit`
  are now constructor parameters (backward-compatible), enabling offline testing
  and agent-driven runs.
- **`divi_migrator/testing/harness.py`** — `FakeWPClient` / `FakeDiviOpsClient`
  that subclass the real clients and record every write for integrity assertions.
- **Contributor on-ramp:** `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`,
  GitHub issue templates (bug / feature / converter-support), a PR template,
  `dependabot.yml`, and `scripts/setup_labels.py` to bootstrap
  `good first issue` / `help wanted` / `converter` labels. README now has a
  "🤝 Contributing" section.

### Changed
- The 9 previously-empty orchestrator tests are now real end-to-end tests
  covering audit init, draft creation, resume-after-interruption, discovery
  exclusion, dedup, rollback, bulk rollback, no-force-delete, full-pipeline
  integrity, and dry-run safety. Unit suite is now 67 tests, all green.

## [0.1.3] - 2026-08-12

### Fixed
- **Design-system colors are now fetched live and never hardcoded.** Removed all
  hardcoded hex fallbacks (including brand colors in `DesignSystem.defaults()` and
  the `"#ffffff"` background fallback in `_get_primary_bg_color`). The inspector
  resolves global colors from the **live Divi Customizer**, then backfills any
  gaps from the **current Home page** (`_backfill_from_home_page`). Unresolved
  colors resolve to `None` and the relevant verification check is skipped rather
  than injecting a guess.
- **Author-based cleanup now targets the right user.** `divi-migrate cleanup
  --author` previously hardcoded author `292` (a site-specific leftover). It now
  defaults to the authenticated migration user's ID (via `wp/v2/users/me`), so it
  reliably targets exactly what the tool created.
- **CLI version reporting** (`divi-migrate --version`) was stuck at `0.1.0` due to
  a stale `__version__` in `__init__.py`; now consistent with `pyproject.toml`.
- **CLI help strings** referenced the wrong console script name (`divi-migrator`
  → `divi-migrate`).

### Changed
- **Author preservation is now explicit.** Migrated pages and posts are created
  without an `author` field, so WordPress assigns the migration user as author
  (the original author is preserved only in the audit trail for rollback). This
  gives reliable, visual identification of migrated content, and the end user can
  bulk-edit the author or bulk-delete via `divi-migrate cleanup --author`.
- **`batch_size` is now wired into audit-discovery pagination** (orchestrator +
  CLI `audit-init`), replacing hardcoded page sizes. It remains capped-aware for
  shared hosts (default 50, fetched per original author).

### Removed
- **Dead `max_content_length` config key** (defined and threaded through the
  credentials layer but never consumed). Removed from `config.py`,
  `credentials/core.py`, `credentials/prompts.py`, `config.yaml`, and the example.
- **Dead `primary_color_override` / `section_bg_override` config keys** (never
  read by any code path).
- **Dead `default_section_bg` config key** (hardcoded `#f7f4ef`, never referenced).

### Docs
- `FUSION_TO_DIVI_MAPPING.md` moved to `docs/` as a maintainer/agent reference and
  rewritten to reflect the actual converter state (basic modules emit native Divi
  5 blocks; advanced modules such as person/faq/tabs emit semantic HTML inside a
  `divi/text` block because their native Divi equivalents don't render headless on
  this host). README now links to it.
- README "Known Limitations" documents the live design-system fetch behavior and
  the author-preservation / bulk-edit workflow.

## [0.1.2] - 2026-08 (prior session)

### Added
- Generic Avada / Plain HTML → Divi 5 migration framework (Elementor converter is
  an honest stub).
- Audit/checkpoint/rollback safety system, author-aware discovery, and a
  token-bucket rate limiter for shared hosts.
- `divi-migrate` CLI: `audit-init`, `discover`, `migrate`, `rollback`, `cleanup`,
  `status`, `doctor`.
- Design System Inspector (Divi Customizer token fetch) and verification engine.
- Strict `mypy --strict` type checking, ruff lint/format, and a unit test suite.
- OIDC trusted publishing to PyPI and a tag-gated Release workflow.

### Notes
- Earlier `0.1.0` / `0.1.1` were yanked from PyPI (versions already existed);
  `0.1.2` is the first published release on the renamed `chriscstewart/Divi-Migrator`
  repository.

[0.1.3]: https://github.com/chriscstewart/Divi-Migrator/releases/tag/v0.1.3
[0.1.2]: https://github.com/chriscstewart/Divi-Migrator/releases/tag/v0.1.2
[0.1.4]: https://github.com/chriscstewart/Divi-Migrator/releases/tag/v0.1.4
[Unreleased]: https://github.com/chriscstewart/Divi-Migrator/compare/v0.1.4...HEAD
