#!/usr/bin/env python
"""Bootstrap standard issue/PR labels on the Divi Migrator repo via the `gh` CLI.

Run once (requires the GitHub CLI authenticated with write access):

    python scripts/setup_labels.py

Idempotent: existing labels are updated, missing ones are created.
"""
from __future__ import annotations

import json
import subprocess
import sys

# label -> (color, description)
LABELS: dict[str, tuple[str, str]] = {
    "bug": ("d73a4a", "Something isn't working"),
    "enhancement": ("a2eeef", "New feature or request"),
    "converter": ("bfd4f2", "Converter support (Avada/Elementor/HTML)"),
    "good first issue": ("7057ff", "Good for newcomers — small, well-bounded task"),
    "help wanted": ("008672", "Extra attention is appreciated"),
    "documentation": ("0075ca", "Docs improvements or additions"),
    "testing": ("c5def5", "Test harness / offline simulation"),
    "security": ("b60205", "Security-sensitive — do not discuss publicly"),
    "wontfix": ("ffffff", "This will not be worked on"),
    "dependencies": ("0366d6", "Pull requests that update a dependency"),
}

REPO = "chriscstewart/Divi-Migrator"


def run(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout
    except subprocess.CalledProcessError as exc:  # noqa: BLE001
        print(f"ERROR running {' '.join(cmd)}:\n{exc.stderr}", file=sys.stderr)
        raise SystemExit(1) from None


def main() -> None:
    if subprocess.run(["gh", "auth", "status"], capture_output=True, check=False).returncode != 0:
        print("`gh` CLI not authenticated. Run `gh auth login` first.", file=sys.stderr)
        raise SystemExit(1)

    existing: set[str] = set()
    try:
        raw = run(["gh", "label", "list", "--repo", REPO, "--json", "name"])
        existing = {d["name"] for d in json.loads(raw)}
    except SystemExit:
        # fall through; we'll attempt to create and tolerate failures
        pass

    for name, (color, desc) in LABELS.items():
        if name in existing:
            run([
                "gh", "label", "edit", name, "--repo", REPO,
                "--color", color, "--description", desc,
            ])
            print(f"updated: {name}")
        else:
            run([
                "gh", "label", "create", name, "--repo", REPO,
                "--color", color, "--description", desc,
            ])
            print(f"created: {name}")

    print(f"\nDone. Labels configured on {REPO}.")


if __name__ == "__main__":
    main()
