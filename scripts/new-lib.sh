#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

read -rp "Library name (kebab-case, will be prefixed with 'voltwire-' if needed): " NAME_INPUT

if [[ "$NAME_INPUT" == voltwire-* ]]; then
    LIBRARY_NAME="$NAME_INPUT"
else
    LIBRARY_NAME="voltwire-$NAME_INPUT"
fi

if [[ ! "$LIBRARY_NAME" =~ ^voltwire-[a-z0-9]+(-[a-z0-9]+)*$ ]]; then
    echo "Error: Name must be kebab-case (lowercase letters, numbers, hyphens only)"
    exit 1
fi

read -rp "Description: " DESCRIPTION

echo "Creating library: $LIBRARY_NAME"

mkdir -p "$LIBRARY_NAME"

# Parse kebab parts (excluding voltwire- prefix) into a src module path
KEBAB_PARTS=$(echo "$LIBRARY_NAME" | sed 's/^voltwire-//' | tr '-' '\n')
MODULE_PATH="src/voltwire"
for PART in $KEBAB_PARTS; do
    MODULE_PATH="$MODULE_PATH/$PART"
done

mkdir -p "$LIBRARY_NAME/$MODULE_PATH"

cat > "$LIBRARY_NAME/$MODULE_PATH/__init__.py" << EOF
__version__ = "0.0.0"
EOF

cat > "$LIBRARY_NAME/pyproject.toml" << EOF
[project]
name = "$LIBRARY_NAME"
version = "0.0.0"
description = "$DESCRIPTION"
authors = [{name = "Hermann Steidel", email = "hsteidel.software@gmail.com"}]
license = "MIT"
requires-python = ">=3.13,<4.0"
dependencies = []

[dependency-groups]
dev = ["pytest>=8.0"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/voltwire"]
EOF

mkdir -p "$LIBRARY_NAME/tests"

IMPORT_PATH="voltwire"
for PART in $KEBAB_PARTS; do
    IMPORT_PATH="$IMPORT_PATH.$PART"
done

cat > "$LIBRARY_NAME/tests/test_sample.py" << EOF
from $IMPORT_PATH import __version__


def test_version():
    assert isinstance(__version__, str)
    assert len(__version__) > 0
EOF

# Register the new package with the root uv workspace
python3 - "$LIBRARY_NAME" << 'PYEOF'
import re
import sys

lib_name = sys.argv[1]
path = "pyproject.toml"
with open(path) as f:
    content = f.read()

if f'"{lib_name}"' in content:
    print("Library already registered in workspace pyproject.toml")
else:
    content = content.replace(
        "members = [\n",
        f"members = [\n    \"{lib_name}\",\n",
        1,
    )
    with open(path, "w") as f:
        f.write(content)
    print("Registered library in workspace pyproject.toml")
PYEOF

echo ""
echo "Library '$LIBRARY_NAME' created successfully!"
echo "  - Folder: $LIBRARY_NAME/"
echo "  - Source: $MODULE_PATH/"
echo "Run 'uv sync' to pick it up."
