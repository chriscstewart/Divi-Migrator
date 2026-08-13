# Contributing to Divi Migrator

Thanks for your interest in Divi Migrator! This is an **open migration
toolchain for moving WordPress sites off Avada / Elementor / plain HTML onto
Divi 5** — built to be run by humans *and* AI agents. Whether you're a WordPress
developer who wants a safer migration path, or you want to extend converter
coverage, your help is welcome.

> **Maturity note.** This project is EXPERIMENTAL. Treat every destructive
> operation as a real migration of someone's live content. The tool's safety
> model (audit-first, draft-then-publish, never force-delete) exists precisely
> so contributions can be tested safely. Read [README.md](./README.md) first.

---

## Why contribute

- **It scratches a real, widespread itch.** Avada → Divi 5 is a painful manual
  rebuild for a lot of agencies. A reusable, auditable converter saves real
  billable hours.
- **It's agent-native.** The CLI and the offline `simulate` harness are designed
  so AI coding agents can run, test, and extend the pipeline without a live site.
  If you build agents, this is a concrete, well-typed surface to wire into.
- **Small, well-bounded surface.** One orchestrator, a converter registry, and a
  fake-WP harness. You can onboard in an afternoon.

---

## Quick start

```bash
# 1. Clone (repo is public)
git clone https://github.com/chriscstewart/Divi-Migrator.git
cd Divi-Migrator

# 2. Create a venv + install dev deps
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 3. Install the secret-scanner pre-commit hook (blocks accidental creds)
pre-commit install

# 4. Verify the gate locally (must match CI before you open a PR)
make check      # ruff check + ruff format --check + mypy --strict
make test       # pytest tests/unit/
make simulate    # offline end-to-end integrity scorecard
```

If `make` isn't available, run the underlying commands directly (see
[README.md → Testing](./README.md#-testing)).

---

## How the code is organized

| Path | Role |
|------|------|
| `divi_migrator/core/orchestrator.py` | `MigrationOrchestrator` — the full pipeline (audit → convert → validate → draft → verify → publish → rename). Clients are **injectable** (`wp`, `diviops`, `audit` params). |
| `divi_migrator/converters/` | Format-specific converters. `avada.py` is the reference implementation; `elementor.py` and `plain_html.py` are starting points. |
| `divi_migrator/converters/base.py` | `BaseConverter` ABC + `ExtractedAssets`. Subclass this to add a source format. |
| `divi_migrator/core/client.py` | `WPClient` (WP REST) + `DiviOpsClient` (DiviOps MCP surfaces used for design-system + block validation). |
| `divi_migrator/core/schema_validator.py` | Validates generated `<!-- wp:divi/... -->` markup against the expected block shape. |
| `divi_migrator/testing/harness.py` | `FakeWPClient` / `FakeDiviOpsClient` — in-memory stand-ins that subclass the real clients. Used by `simulate` and the orchestrator tests. |
| `docs/FUSION_TO_DIVI_MAPPING.md` | Authoritative Avada-shortcode → Divi 5 module capability map. |

---

## Development workflow

1. **Branch off `develop`** (or `main` if `develop` is behind). Name branches
   `feat/...`, `fix/...`, `docs/...`.
2. **Keep the gate green.** Every commit must pass `ruff`, `ruff format`,
   `mypy --strict`, and `pytest tests/unit/`. CI enforces the same on PRs.
3. **Test offline first.** Use `make simulate` for an end-to-end run, and add a
   test in `tests/unit/` that uses `divi_migrator.testing.harness`. No live
   WordPress site is required to contribute.
4. **Add a test for behavior, not just coverage.** The harness records every
   write — assert on integrity (e.g. originals are renamed, never force-deleted).
5. **Update docs.** Converter changes → update `docs/FUSION_TO_DIVI_MAPPING.md`.
   User-facing changes → add a `CHANGELOG.md` entry under `Unreleased`.

### Adding a converter (the most likely contribution)

```python
from divi_migrator.converters.base import BaseConverter

class MyFormatConverter(BaseConverter):
    format_name = "my_format"

    def detect(self, content: str) -> bool:
        return "some-marker" in content

    def convert(self, content, source_id, design_system=None, wp_client=None) -> str:
        # Emit <!-- wp:divi/... --> markup. Use base._wrap_as_plain_html()
        # for a safe fallback, or build native blocks for full fidelity.
        ...

    def extract_assets(self, content: str) -> ExtractedAssets:
        ...
```

Then register it and add a fixture + a `simulate`-style test. See
`converters/avada.py` for the reference shape.

---

## Commit / PR conventions

- **Conventional-ish commits** are appreciated but not enforced:
  `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`.
- **PRs must**:
  - target `develop` (or `main`),
  - pass the full CI gate (ruff / format / mypy --strict / pytest),
  - include tests for new behavior,
  - update `CHANGELOG.md` (add an `## [Unreleased]` section if absent),
  - never commit secrets (the pre-commit hook blocks `.env` and credential
    patterns; use `.env.example` for placeholders).
- Use the PR template — it is filled in automatically.

---

## Releasing (maintainers)

Releases are **tag-driven** and automated:

1. Bump `__version__` in `divi_migrator/__init__.py`.
2. Add a `## [x.y.z] - YYYY-MM-DD` entry to `CHANGELOG.md` (Keep a Changelog
   format, SemVer).
3. Commit, then tag and push:
   ```bash
   git tag v0.2.0
   git push origin v0.2.0
   ```
4. The `release.yml` workflow runs the CI gate, builds the sdist/wheel,
   publishes to PyPI via **OIDC trusted publishing** (no password in the repo),
   and drafts a GitHub Release.

> **PyPI note.** Versions already published to PyPI cannot be re-uploaded. Always
> bump the version before a new release. The repo is public; the published
> package lives at `https://pypi.org/project/divi-migrator/`.

---

## Good first issues

Look for the **`good first issue`** and **`help wanted`** labels. Top starter
tasks right now:

- Expand `docs/FUSION_TO_DIVI_MAPPING.md` with before/after markup examples.
- Improve the Elementor converter (`converters/elementor.py`) — it's a starting
  point, not feature-complete.
- Add golden-output snapshot tests using `divi_migrator.testing.harness`.
- Harden the `simulate` scorecard (e.g. coverage % of shortcodes converted).

Run `scripts/setup_labels.py` once to bootstrap the standard labels on the repo
(requires the `gh` CLI and write access).

---

## Code of conduct

This project follows the [Contributor Covenant](./CODE_OF_CONDUCT.md). Be
respectful; assume good faith; prioritize safe, reversible migrations.

## Security

Found a vulnerability? **Do not open a public issue.** See
[SECURITY.md](./SECURITY.md) for private disclosure instructions.
