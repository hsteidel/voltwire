#!/usr/bin/env bash
set -e

usage() {
    echo "Usage: $0 <package-dir> <patch|minor|major>"
    echo "Example: $0 voltwire-db-session patch"
    exit 1
}

PACKAGE="$1"
BUMP="$2"

[[ -z "$PACKAGE" || -z "$BUMP" ]] && usage
[[ "$BUMP" != "patch" && "$BUMP" != "minor" && "$BUMP" != "major" ]] && usage

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
PACKAGE_DIR="$ROOT_DIR/$PACKAGE"

[[ -d "$PACKAGE_DIR" ]] || { echo "Error: $PACKAGE_DIR does not exist"; exit 1; }

if [[ -n "$(git -C "$ROOT_DIR" status --porcelain)" ]]; then
    echo "Error: working tree is not clean. Commit or stash changes first."
    exit 1
fi

cd "$PACKAGE_DIR"

echo "Running tests..."
uv run pytest

echo "Bumping version ($BUMP)..."
uv version --bump "$BUMP"
VERSION=$(uv version --short)
TAG="${PACKAGE}-v${VERSION}"

if git -C "$ROOT_DIR" rev-parse "$TAG" >/dev/null 2>&1; then
    echo "Tag $TAG already exists — aborting"
    git -C "$ROOT_DIR" checkout -- "$PACKAGE_DIR/pyproject.toml"
    exit 1
fi

echo "Building..."
uv build

echo "Committing and tagging..."
git -C "$ROOT_DIR" add "$PACKAGE_DIR/pyproject.toml"
git -C "$ROOT_DIR" commit -m "release: bump $PACKAGE to v${VERSION}"
git -C "$ROOT_DIR" tag "$TAG"

echo "Publishing to PyPI..."
uv publish

echo ""
echo "Done. Published $PACKAGE v${VERSION} as tag $TAG."
echo "Push with: git push origin HEAD --tags"
