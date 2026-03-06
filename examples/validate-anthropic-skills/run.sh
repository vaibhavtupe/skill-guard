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

echo "Validating each skill in $SKILLS_DIR ..."
for skill_dir in "$SKILLS_DIR"/*/; do
  echo ""
  echo "── $(basename "$skill_dir") ──"
  skill-guard validate "$skill_dir"
done

if [ "${1:-}" = "--with-conflict" ]; then
  echo ""
  echo "── Conflict detection ──"
  for skill_dir in "$SKILLS_DIR"/*/; do
    skill-guard conflict "$skill_dir" --against "$SKILLS_DIR"
  done
fi
