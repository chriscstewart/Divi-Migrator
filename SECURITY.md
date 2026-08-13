# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| latest  | :white_check_mark: |
| older   | :x:                |

## Reporting a Vulnerability

**Do not report security vulnerabilities in public GitHub issues.**

Divi Migrator performs destructive migrations of real WordPress content, so a
vulnerability (e.g. credential handling, an unintended force-delete, or an
audit-bypass) could cause data loss for users.

Please report privately via **GitHub Security Advisories**:

1. Go to the repository → **Security** → **Advisories** → **New draft security
   advisory**.
2. Describe the vulnerability, impact, and a minimal reproduction.
3. The maintainer will acknowledge within a few days and coordinate a fix and
   coordinated disclosure.

If you cannot use a security advisory, email the maintainer (see
`CODE_OF_CONDUCT.md` contact) with `[SECURITY]` in the subject.

## Scope notes

- **Secrets:** Credentials belong in the git-ignored `.env` / environment
  variables, never in source. The repo ships a `pre-commit` secret scanner;
  PRs that reintroduce credentials are blocked.
- **Non-security bugs** (conversion errors, UI issues) should use the public
  bug-report template, not this policy.
