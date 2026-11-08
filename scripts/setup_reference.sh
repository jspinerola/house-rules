#!/usr/bin/env bash
# Clone the PNC workshop repo into reference/ (gitignored, read-only) and
# seed brain/wellness/ from it if our working copy is missing.
set -euo pipefail
cd "$(dirname "$0")/.."

REPO_URL="https://github.com/devfulcrum/pnc-utd-hackathon-2026"
DEST="reference/pnc-workshop"

if [ -d "$DEST" ]; then
  echo "$DEST already exists; skipping clone"
else
  mkdir -p reference
  git clone --depth 1 "$REPO_URL" "$DEST"
  rm -rf "$DEST/.git"
  echo "cloned workshop into $DEST"
fi

if [ ! -d brain/wellness ]; then
  cp -r "$DEST/wellness" brain/wellness
  echo "copied wellness/ into brain/wellness"
fi
