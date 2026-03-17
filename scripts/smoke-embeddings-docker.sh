#!/usr/bin/env bash
set -euo pipefail

# Docker-based smoke for embeddings (Linux + torch). Matches README usage.
# Requires Docker.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="python:3.12-slim"

set -x

docker run --rm \
  -v "$ROOT":/work \
  -w /work \
  "$IMAGE" \
  bash -lc "python -m pip install --upgrade pip && \
            python -m pip install --index-url https://download.pytorch.org/whl/cpu torch==2.4.0 && \
            python -m pip install 'skill-guard[embeddings]==0.6.0' && \
            skill-guard validate tests/fixtures/skills/valid-skill && \
            skill-guard secure tests/fixtures/skills/valid-skill && \
            skill-guard conflict tests/fixtures/skills/valid-skill --against tests/fixtures/skills/injection-skill && \
            skill-guard conflict tests/fixtures/skills/valid-skill --against tests/fixtures/skills/injection-skill --method embeddings && \
            skill-guard check tests/fixtures/skills/valid-skill --against tests/fixtures/skills/injection-skill && \
            TMPDIR=\$(mktemp -d) && cd \"\$TMPDIR\" && skill-guard init"

echo "✅ docker embeddings smoke passed"
