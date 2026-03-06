#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/tmp/anthropics-skills"
SKILLS_DIR="$REPO_DIR/skills"

if [ -d "$REPO_DIR/.git" ]; then
  git -C "$REPO_DIR" pull --ff-only
else
  rm -rf "$REPO_DIR"
  git clone https://github.com/anthropics/skills "$REPO_DIR"
fi

skill-guard validate --dir "$SKILLS_DIR"

if [ "${1:-}" = "--with-conflict" ]; then
  skill-guard conflict --dir "$SKILLS_DIR"
fi
