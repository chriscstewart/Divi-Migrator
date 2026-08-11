#!/usr/bin/env python3
"""Pre-commit secret scanner.

Fails if a staged file contains an obvious secret assignment (password /
secret / token / app_password with a non-trivial value). Intent: catch
accidental commits of credentials. This is a cheap safety net, not a
substitute for proper secret management (secrets belong in `.env` / env vars).

Skip a specific line with a trailing `# pragma: allow-secret` comment.
"""

import re
import sys
from pathlib import Path

# A secret assignment = a secret-style key followed by a QUOTED literal value
# of >= 8 chars. Requiring quotes avoids flagging code references such as
# `os.environ["WP_APP_PASSWORD"]` or `x = explicit["wp_app_password"]`, where the
# value is a variable expression, not a literal secret. We intentionally do NOT
# match a bare `token` key (too broad: color tokens, etc.); only the explicit
# secret-bearing key names below.
SECRET_PATTERNS = [
    re.compile(
        r"(?i)(app_password|password|passwd|secret|api[_-]?key|access[_-]?key|"
        r"private[_-]?key)\s*[:=]\s*['\"]([A-Za-z0-9_=+/.\-]{8,})['\"]"
    ),
    re.compile(
        r"(?i)(wp_app_password|diviops_app_password)\s*[:=]\s*['\"]"
        r"([A-Za-z0-9_=+/.\-]{8,})['\"]"
    ),
]

# Values that are obviously placeholders and should NOT trip the scanner.
PLACEHOLDER_VALUES = {
    "",
    "example",
    "changeme",
    "replace_with_your_app_password",
    "replace_with_your_live_app_password",
    "your-application-password-no-spaces",
    "your-wp-username",
}

SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "audit_backups",
    "checkpoints",
    ".ruff_cache",
    ".mypy_cache",
}
SKIP_EXT = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".pdf",
    ".woff",
    ".woff2",
    ".ttf",
    ".ico",
    ".lock",
    ".pyc",
}


def scan(path: Path) -> list[str]:
    if any(part in SKIP_DIRS for part in path.parts):
        return []
    if path.suffix.lower() in SKIP_EXT:
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except (OSError, UnicodeDecodeError):
        return []
    issues: list[str] = []
    for i, line in enumerate(text.splitlines(), 1):
        if "# pragma: allow-secret" in line:
            continue
        for pat in SECRET_PATTERNS:
            m = pat.search(line)
            if m and m.group(2).strip().lower() not in PLACEHOLDER_VALUES:
                issues.append(f"{path}:{i}: {line.strip()[:120]}")
                break
    return issues


def main() -> int:
    files = sys.argv[1:] or [str(p) for p in Path(".").rglob("*")]
    all_issues: list[str] = []
    for f in files:
        p = Path(f)
        if p.is_file():
            all_issues.extend(scan(p))
    if all_issues:
        print("ERROR: possible secrets found in files:", file=sys.stderr)
        for iss in all_issues:
            print("  " + iss, file=sys.stderr)
        print(
            "\nIf this is a false positive, add `# pragma: allow-secret` to the line.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
