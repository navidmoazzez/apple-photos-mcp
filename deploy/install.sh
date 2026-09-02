#!/usr/bin/env bash
# Install the server into Claude Code and check it can reach the library.
#
# One command each. It exists so nobody has to read the README to get started.
set -euo pipefail

PKG="@thenavidm/apple-photos-mcp-cli@latest"

[ "$(uname)" = "Darwin" ] || {
  echo "Apple Photos only exists on macOS, so this server cannot run here." >&2
  exit 1
}

command -v node >/dev/null 2>&1 || {
  echo "Node 20 or newer is required. https://nodejs.org" >&2
  exit 1
}

MAJOR="$(node -p 'process.versions.node.split(".")[0]')"
if [ "$MAJOR" -lt 20 ]; then
  echo "Node 20 or newer is required, found $(node -v)." >&2
  exit 1
fi

# uv fetches the Python engine's dependencies on first run. They are macOS-only
# and build pyobjc, which is why they are not vendored.
command -v uv >/dev/null 2>&1 || {
  echo "Installing uv, which fetches the Photos engine on first run..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
}

echo "Registering the MCP server with Claude Code..."
if command -v claude >/dev/null 2>&1; then
  claude mcp add apple-photos --scope user -- npx -y "$PKG"
else
  echo "The claude CLI is not installed, so nothing was registered."
  echo "Add this to your client's config yourself:"
  echo "  command: npx"
  echo "  args:    -y $PKG"
fi

echo
echo "Checking the library. macOS will ask for permission the first time."
npx -y "$PKG" doctor
