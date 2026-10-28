#!/bin/sh
# Install the 1to3d freecad skill, the freecad-designer agent and the FreeCAD MCP server into Kilo Code.
#
#   curl -fsSL https://raw.githubusercontent.com/satinjeet/1to3d/main/install.sh | sh
#   curl -fsSL https://raw.githubusercontent.com/satinjeet/1to3d/main/install.sh | sh -s -- --project <dir>
#   ./install.sh [--project <dir>] [--uninstall]     from a clone
#
# Run from a clone, it installs that clone's files. Piped from curl, it downloads the repo first
# (branch or tag from ONETO3D_REF, default main) into a temporary folder.
#
# Files are copied, not linked: Kilo does not follow a symlinked skill folder. Rerun after updating.
#
# What it touches
#   global   ~/.agents/skills/freecad                   copy of skills/freecad
#            ~/.config/kilo/agents/freecad-designer.md  copy of kilo/agents/freecad-designer.md
#            ~/.config/kilo/kilo.json                   adds mcp.freecad (Kilo merges it with kilo.jsonc)
#   project  <dir>/.agents/skills/freecad, <dir>/.kilo/agents/freecad-designer.md, <dir>/.kilo/kilo.json
set -eu

REPO="satinjeet/1to3d"
REF="${ONETO3D_REF:-main}"
MCP_URL="${FREECAD_MCP_URL:-http://127.0.0.1:39280/mcp}"
MODE=global
PROJECT=""
ACTION=install

usage() {
  cat <<EOF
Usage: install.sh [--project <dir>] [--uninstall]

  (no options)       install for every Kilo project on this machine
  --project <dir>    install into one project only
  --uninstall        remove what install added (global, or with --project)

Environment
  FREECAD_MCP_URL    MCP Bridge URL (default http://127.0.0.1:39280/mcp)
  ONETO3D_REF        branch or tag to download when not run from a clone (default main)
EOF
}

die() { echo "install.sh: $*" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --project)
      [ $# -ge 2 ] || die "--project needs a folder"
      MODE=project; PROJECT="$(cd "$2" && pwd)" || die "no such folder: $2"; shift 2 ;;
    --uninstall) ACTION=uninstall; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
done

command -v python3 >/dev/null 2>&1 || die "python3 is required"

case "$REF" in
  ""|-*|*[!A-Za-z0-9._/-]*|*..*) die "ONETO3D_REF must be a branch or tag name, got: $REF" ;;
esac
case "$MCP_URL" in
  http://127.0.0.1:*|http://localhost:*|http://\[::1\]:*) ;;
  *) echo "install.sh: warning: $MCP_URL is not on this machine. The MCP Bridge runs any Python it is sent;" >&2
     echo "install.sh: only point it at a host you trust, over a trusted network." >&2 ;;
esac

# install writes this file into the skill folder; uninstall and reinstall only delete a folder that has it,
# so a different skill that happens to be called "freecad" is never removed.
MARKER=".installed-by-1to3d"

if [ "$MODE" = global ]; then
  SKILLS="$HOME/.agents/skills"
  AGENTS="${XDG_CONFIG_HOME:-$HOME/.config}/kilo/agents"
  CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/kilo/kilo.json"
else
  SKILLS="$PROJECT/.agents/skills"
  AGENTS="$PROJECT/.kilo/agents"
  CONFIG="$PROJECT/.kilo/kilo.json"
fi

# Add or remove mcp.freecad in a plain JSON config, keeping everything else in it.
# An mcp.freecad that does not point at $MCP_URL (or was hand-edited) is the user's own and is left alone.
# The old file is kept as <config>.bak and the new one is written to a temp file and renamed into place.
edit_mcp() {
  python3 - "$CONFIG" "$1" "$MCP_URL" <<'EOF'
import json, os, shutil, sys, tempfile
path, action, url = sys.argv[1:]
ours = {"type": "remote", "url": url, "enabled": True, "timeout": 120000}
cfg = {}
if os.path.exists(path):
    with open(path) as f:
        cfg = json.load(f)
cur = cfg.get("mcp", {}).get("freecad")
if cur is not None and cur != ours:
    print("install.sh: %s has an mcp.freecad that 1to3d did not write; leaving it as is" % path, file=sys.stderr)
    sys.exit()
if action == "add":
    if cur == ours:
        sys.exit()
    cfg.setdefault("$schema", "https://app.kilo.ai/config.json")
    cfg.setdefault("mcp", {})["freecad"] = ours
elif cur is None:
    sys.exit()
else:
    cfg["mcp"].pop("freecad")
    if cfg["mcp"] == {}:
        cfg.pop("mcp")
d = os.path.dirname(path)
os.makedirs(d, exist_ok=True)
if os.path.exists(path):
    shutil.copy2(path, path + ".bak")
fd, tmp = tempfile.mkstemp(dir=d, prefix=".kilo.json.")
with os.fdopen(fd, "w") as f:
    json.dump(cfg, f, indent=2)
    f.write("\n")
os.replace(tmp, path)
EOF
}

# Delete the installed skill folder, but only if this installer made it.
remove_skill() {
  [ -e "$SKILLS/freecad" ] || return 0
  [ -f "$SKILLS/freecad/$MARKER" ] || die "$SKILLS/freecad was not installed by 1to3d; move it away first"
  rm -rf "$SKILLS/freecad"
}

if [ "$ACTION" = uninstall ]; then
  remove_skill
  rm -f "$AGENTS/freecad-designer.md"
  edit_mcp remove
  echo "removed 1to3d from Kilo ($MODE)"
  exit 0
fi

# Use the clone this script sits in, or download the repo when piped from curl.
ROOT=""
if [ "$(basename "$0")" = install.sh ] && [ -f "$0" ]; then
  ROOT="$(cd "$(dirname "$0")" && pwd)"
  [ -f "$ROOT/skills/freecad/SKILL.md" ] || ROOT=""
fi
if [ -z "$ROOT" ]; then
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  URL="https://github.com/$REPO/archive/$REF.tar.gz"
  echo "downloading $REPO@$REF"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL -o "$TMP/repo.tar.gz" "$URL" || die "could not download $URL"
  elif command -v wget >/dev/null 2>&1; then
    wget -qO "$TMP/repo.tar.gz" "$URL" || die "could not download $URL"
  else
    die "curl or wget is required"
  fi
  mkdir "$TMP/repo"
  tar -xzf "$TMP/repo.tar.gz" -C "$TMP/repo" --strip-components=1 2>/dev/null \
    || die "$URL is not a tarball; check the repo is public and $REF exists"
  ROOT="$TMP/repo"
  [ -f "$ROOT/skills/freecad/SKILL.md" ] || die "download from $URL has no skills/freecad"
fi

mkdir -p "$SKILLS" "$AGENTS"
remove_skill
cp -r "$ROOT/skills/freecad" "$SKILLS/freecad"
find "$SKILLS/freecad" -name __pycache__ -prune -exec rm -rf {} +
echo "$REPO@$REF" > "$SKILLS/freecad/$MARKER"
cp "$ROOT/kilo/agents/freecad-designer.md" "$AGENTS/freecad-designer.md"
edit_mcp add

echo "installed 1to3d for Kilo ($MODE)"
echo "  skill  $SKILLS/freecad"
echo "  agent  $AGENTS/freecad-designer.md"
echo "  mcp    freecad -> $MCP_URL in $CONFIG"
echo "Reload the Kilo panel (or restart kilo), then pick the freecad-designer agent."
