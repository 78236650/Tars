#!/usr/bin/env bash
# Migrate legacy Evolution files from ~/.tars/workspaces to ~/.tars/agents
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$ROOT/backend/.venv/bin/python"
if [[ ! -x "$VENV" ]]; then
  VENV="python3"
fi

cd "$ROOT/backend"
$VENV -c "
from tars.evolution.workspace_migration import migrate_legacy_workspace
migrated = migrate_legacy_workspace(force=False)
print('Migrated files:', len(migrated))
for path in migrated:
    print(' ', path)
"
