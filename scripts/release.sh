#!/usr/bin/env bash
set -euo pipefail

# Tags have no "v" prefix — publish.yml uses the tag name directly as the PEP 440 version.

# Determine the last release tag (X.Y.Z), or use the initial commit if none exist.
LAST_TAG="$(git tag --list '[0-9]*' --sort=-version:refname | head -1)"
if [[ -z "$LAST_TAG" ]]; then
  RANGE=""
  SINCE_DESC="the beginning"
else
  RANGE="${LAST_TAG}..HEAD"
  SINCE_DESC="$LAST_TAG"
fi

# Collect commits since last release
echo "Commits since ${SINCE_DESC}:"
echo "---"
git log ${RANGE:+"$RANGE"} --oneline
echo "---"
echo ""

# Prompt for the new version
read -r -p "New version (e.g. 0.2.0): " NEW_VERSION
if [[ -z "$NEW_VERSION" ]]; then
  echo "No version provided, aborting." >&2
  exit 1
fi

# Build draft release notes
TMPFILE="$(mktemp)"
trap 'rm -f "$TMPFILE"' EXIT

{
  echo "# Release ${NEW_VERSION}"
  echo ""
  echo "## Changes"
  echo ""
  git log ${RANGE:+"$RANGE"} --format="- %s" --reverse
} > "$TMPFILE"

# Open editor for cleanup
"${EDITOR:-vi}" "$TMPFILE"

if [[ ! -s "$TMPFILE" ]]; then
  echo "Empty release notes, aborting." >&2
  exit 1
fi

RELEASE_NOTES="$(cat "$TMPFILE")"

echo ""
echo "=== Release notes ==="
echo "$RELEASE_NOTES"
echo "====================="
echo ""

read -r -p "Create release ${NEW_VERSION}? [y/N] " CONFIRM
if [[ "$CONFIRM" != [yY] ]]; then
  echo "Aborted." >&2
  exit 1
fi

# Tag and push
git tag -a "${NEW_VERSION}" -m "${NEW_VERSION}"
git push origin "${NEW_VERSION}"

echo ""
echo "Creating GitHub release..."
gh release create "${NEW_VERSION}" --title "${NEW_VERSION}" --notes "$RELEASE_NOTES"
echo "Done! https://github.com/JacobHayes/pydantic-settings-op/releases/tag/${NEW_VERSION}"
