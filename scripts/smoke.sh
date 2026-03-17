#!/usr/bin/env bash
set -euo pipefail

# Local smoke (no embeddings) using Python 3.12 venv managed by uv.
# Creates .venv312 if missing.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ ! -d .venv312 ]; then
  uv python install 3.12
  uv venv --python 3.12 .venv312
fi

source .venv312/bin/activate
python -m ensurepip --upgrade >/dev/null 2>&1 || true
python -m pip install --upgrade pip
python -m pip install "skill-guard==0.6.0"

# README-aligned smoke
skill-guard validate tests/fixtures/skills/valid-skill
skill-guard secure tests/fixtures/skills/valid-skill
skill-guard conflict tests/fixtures/skills/valid-skill --against tests/fixtures/skills/injection-skill
skill-guard check tests/fixtures/skills/valid-skill --against tests/fixtures/skills/injection-skill

TMPDIR=$(mktemp -d)
(cd "$TMPDIR" && skill-guard init)

echo "✅ local smoke (no embeddings) passed"
