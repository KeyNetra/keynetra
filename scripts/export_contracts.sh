#!/bin/bash

set -e

# --- Configuration ---
OUTPUT_DIR="contracts/openapi"
JSON_OUTPUT="$OUTPUT_DIR/openapi.json"
YAML_OUTPUT="$OUTPUT_DIR/openapi.yaml"

echo "--------------------------------------------------"
echo "🚀 Exporting KeyNetra OpenAPI Contracts..."
echo "--------------------------------------------------"

# Ensure the output directory exists
mkdir -p "$OUTPUT_DIR"

# Export OpenAPI JSON and YAML using the KeyNetra CLI
# Assuming keynetra is installed in the environment
if command -v keynetra >/dev/null 2>&1; then
    keynetra generate-openapi \
        --output "$JSON_OUTPUT" \
        --yaml-output "$YAML_OUTPUT"
else
    # Fallback to calling python directly if CLI is not in path
    python3 -m keynetra.main generate-openapi \
        --output "$JSON_OUTPUT" \
        --yaml-output "$YAML_OUTPUT"
fi

echo "✅ Contracts exported to:"
echo "   - $JSON_OUTPUT"
echo "   - $YAML_OUTPUT"
echo "--------------------------------------------------"
