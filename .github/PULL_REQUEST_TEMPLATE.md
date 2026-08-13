## Description

<!-- What does this PR do, and why? Link any related issue (e.g. "Closes #12"). -->

## Type of change

- [ ] Bug fix (`fix:`)
- [ ] New feature (`feat:`)
- [ ] Converter support (`converters/...`)
- [ ] Docs / chore
- [ ] Offline simulation / test harness

## Checklist

- [ ] `ruff check .` passes
- [ ] `ruff format --check .` passes
- [ ] `mypy --strict divi_migrator` passes
- [ ] `pytest tests/unit/` passes
- [ ] `python -m divi_migrator.cli simulate` runs and the integrity scorecard passes
- [ ] Added/updated tests for the changed behavior
- [ ] Updated `CHANGELOG.md` (add an `## [Unreleased]` section if missing)
- [ ] Converter changes also updated `docs/FUSION_TO_DIVI_MAPPING.md`
- [ ] No secrets/credentials committed (`.env` stays git-ignored)

## Notes for reviewers

<!-- Anything non-obvious: host-specific quirks, reversible vs destructive steps, etc. -->
