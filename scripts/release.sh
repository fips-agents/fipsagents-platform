#!/usr/bin/env bash
# Bump version, commit, tag, and push.
#
# Usage:
#   scripts/release.sh <version> "<description>"
#
# Updates src/fipsagents_platform/version.py and pyproject.toml to <version>,
# commits with a release message, creates an annotated v<version> tag, and
# pushes both main and the tag. The release.yml workflow handles build +
# GitHub Release + (future) container publish on the tag push.

set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "usage: scripts/release.sh <version> \"<description>\"" >&2
  exit 2
fi

VERSION="$1"
DESCRIPTION="$2"

if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "error: version must be semver major.minor.patch (got: $VERSION)" >&2
  exit 2
fi

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$BRANCH" != "main" ]]; then
  echo "error: must release from main (currently on: $BRANCH)" >&2
  exit 2
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "error: working tree not clean" >&2
  exit 2
fi

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

VERSION_PY="src/fipsagents_platform/version.py"
PYPROJECT="pyproject.toml"

echo "Updating version to $VERSION..."
python3 -c "
import re, pathlib
p = pathlib.Path('$VERSION_PY')
p.write_text(re.sub(r'__version__ = \"[^\"]+\"', '__version__ = \"$VERSION\"', p.read_text()))
"
python3 -c "
import re, pathlib
p = pathlib.Path('$PYPROJECT')
p.write_text(re.sub(r'^version = \"[^\"]+\"', 'version = \"$VERSION\"', p.read_text(), count=1, flags=re.MULTILINE))
"

# Verify both files agree.
PY_VER="$(python3 -c "exec(open('$VERSION_PY').read()); print(__version__)")"
TOML_VER="$(grep '^version =' "$PYPROJECT" | head -1 | sed -E 's/version = "([^"]+)"/\1/')"
if [[ "$PY_VER" != "$VERSION" || "$TOML_VER" != "$VERSION" ]]; then
  echo "error: version sync failed (py=$PY_VER toml=$TOML_VER target=$VERSION)" >&2
  exit 1
fi

git add "$VERSION_PY" "$PYPROJECT"
if git diff --cached --quiet; then
  echo "Version files already at $VERSION; tagging current HEAD without a release commit."
else
  git commit -m "release: v$VERSION — $DESCRIPTION

Assisted-by: Claude Code (Opus 4.7)"
fi

git tag -a "v$VERSION" -m "v$VERSION — $DESCRIPTION"

echo "Pushing main and v$VERSION..."
git push origin main
git push origin "v$VERSION"

echo
echo "Released v$VERSION."
echo "  https://github.com/fips-agents/fipsagents-platform/releases/tag/v$VERSION"
