#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
JSON_OUTPUT="$REPO_ROOT/contracts/openapi.json"
YAML_OUTPUT="$REPO_ROOT/contracts/openapi.yaml"

echo "--------------------------------------------------"
echo "🚀 Exporting KeyNetra OpenAPI Contracts..."
echo "--------------------------------------------------"

mkdir -p "$(dirname "$JSON_OUTPUT")"

cd "$REPO_ROOT"

if command -v keynetra >/dev/null 2>&1; then
    keynetra generate-openapi \
        --output "$JSON_OUTPUT" \
        --yaml-output "$YAML_OUTPUT"
else
    python3 -m keynetra generate-openapi \
        --output "$JSON_OUTPUT" \
        --yaml-output "$YAML_OUTPUT"
fi

echo "✅ Contracts exported to:"
echo "   - $JSON_OUTPUT"
echo "   - $YAML_OUTPUT"
echo "--------------------------------------------------"
