#!/usr/bin/env python3
"""Allow CHANGELOG / manifest edits only on a release-please PR.

Used as a required check on `main`. Feature PRs that do not touch those
files always pass. Handmade version bumps fail. See RELEASING.md.
"""

from __future__ import annotations

import argparse
import sys

RELEASE_FILES = frozenset(
    {
        "CHANGELOG.md",
        ".release-please-manifest.json",
    }
)
RELEASE_PLEASE_PREFIX = "release-please--branches--"
ALLOWED_AUTHORS = frozenset(
    {
        "github-actions[bot]",
        "release-please[bot]",
    }
)


def touches_release_artifacts(changed_files: list[str]) -> bool:
    return any(path in RELEASE_FILES for path in changed_files)


def is_release_please_pr(head_ref: str, author: str) -> bool:
    return head_ref.startswith(RELEASE_PLEASE_PREFIX) and author in ALLOWED_AUTHORS


def release_authority_ok(
    changed_files: list[str],
    head_ref: str,
    author: str,
) -> tuple[bool, str]:
    if not touches_release_artifacts(changed_files):
        return True, "no release artifacts changed"
    if is_release_please_pr(head_ref, author):
        return True, "release-please PR"
    return (
        False,
        (
            "CHANGELOG.md and .release-please-manifest.json may only change on "
            "a release-please PR (branch release-please--branches--* opened by "
            "github-actions[bot]). Run Actions → release-please from the GitHub UI."
        ),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--head-ref", required=True)
    parser.add_argument("--author", required=True)
    parser.add_argument("--changed-files", nargs="*", default=[])
    args = parser.parse_args(argv)
    files = list(args.changed_files)
    if not sys.stdin.isatty() and not files:
        files = [line.strip() for line in sys.stdin if line.strip()]
    ok, reason = release_authority_ok(files, args.head_ref, args.author)
    print(reason)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
