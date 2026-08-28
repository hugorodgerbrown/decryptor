#!/usr/bin/env bash
# Deploy build. Produces everything that is NOT in git:
#   .vocab-cache.pkl  the built index          (~19 MB)
#   decryptor.html    single-file build        (~2.2 MB)
#   dist/             the folder you host      (~2.2 MB)
set -euo pipefail

# --frozen: build from uv.lock as committed, never re-resolve mid-build.
# --no-default-groups: a deploy build has no use for tox, ruff or playwright.
uv sync --frozen --no-default-groups --group build
uv run python -c "import nltk; nltk.download('wordnet', quiet=True)"

uv run python vocab.py                            # ~30s
uv run python build_payload.py
uv run python -c "
payload = open('payload.b64').read().strip()
open('decryptor.html','w').write(
    open('ui.template.html').read().replace('__PAYLOAD__', payload))
"
uv run python build_dist.py
echo "build complete"
