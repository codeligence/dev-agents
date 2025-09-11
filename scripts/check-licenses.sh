#!/bin/bash
set -euo pipefail

# License compliance checking script for dev-agents
# This script checks all third-party dependencies for license compliance with AGPL v3

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_PATH="${PROJECT_ROOT}/venv"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🔍 Checking license compliance for dev-agents dependencies..."

# Use virtual environment if exists
if [ -d "$VENV_PATH" ]; then
    source "$VENV_PATH/bin/activate"
fi

# Check if pip-licenses is installed
if ! command -v pip-licenses &> /dev/null; then
    echo "📦 Installing pip-licenses..."
    pip install pip-licenses
fi

# Temporary move pyproject.toml to avoid parsing errors
if [ -f "$PROJECT_ROOT/pyproject.toml" ]; then
    cp "$PROJECT_ROOT/pyproject.toml" "$PROJECT_ROOT/pyproject.toml.backup"
    mv "$PROJECT_ROOT/pyproject.toml" "$PROJECT_ROOT/pyproject.toml.temp"
fi

# Generate license reports
echo "📋 Generating license reports..."

# JSON format for programmatic analysis
pip-licenses --format=json --output-file="$PROJECT_ROOT/licenses_report.json"

# CSV format with URLs for detailed analysis
pip-licenses --format=csv --with-urls --output-file="$PROJECT_ROOT/licenses_detailed.csv"

# Plain table format for human reading
pip-licenses --format=plain-vertical > "$PROJECT_ROOT/licenses_summary.txt"

# Restore pyproject.toml
if [ -f "$PROJECT_ROOT/pyproject.toml.temp" ]; then
    mv "$PROJECT_ROOT/pyproject.toml.temp" "$PROJECT_ROOT/pyproject.toml"
fi

###############################################################################
# Resolve UNKNOWN licenses using a known mapping (name -> license, no versions)
###############################################################################
# NOTE: Keep keys as installed distribution names (what pip-licenses prints in "Name").
# For names that are sometimes hyphen/underscore, include both forms.

cat > "$PROJECT_ROOT/licenses_map.json" <<'JSON'
{
  "ag-ui-protocol": "MIT License",
  "attrs": "MIT License",
  "build": "MIT License",
  "click": "BSD 3-Clause License",
  "fsspec": "BSD 3-Clause License",
  "griffe": "ISC License",
  "jsonschema": "MIT License",
  "jsonschema-specifications": "MIT License",
  "logfire-api": "MIT License",
  "mistralai": "Apache License 2.0",
  "nexus-rpc": "MIT License",
  "opentelemetry-api": "Apache License 2.0",
  "pipdeptree": "MIT License",
  "pytest-asyncio": "Apache License 2.0",
  "referencing": "MIT License",
  "sse-starlette": "BSD 3-Clause License",
  "temporalio": "MIT License",
  "types-protobuf": "Apache License 2.0",
  "types-requests": "Apache License 2.0",
  "typing-inspection": "MIT License",
  "typing-extensions": "Python Software Foundation License",
  "typing_extensions": "Python Software Foundation License",
  "urllib3": "MIT License",
  "zipp": "MIT License",
  "CacheControl": "Apache License 2.0",
  "Markdown": "BSD License",
  "anyio": "MIT License",
  "cz-conventional-gitmoji": "MIT License",
  "hf-xet": "Apache License 2.0",
  "mkdocs-autorefs": "ISC License",
  "mkdocs-social-plugin": "MIT License",
  "mkdocstrings": "ISC License",
  "mkdocstrings-python": "ISC License",
  "mypy_extensions": "MIT License",
  "pillow": "HPND",
  "pytest-xdist": "MIT License",
  "pyyaml_env_tag": "MIT License",
  "rpds-py": "MIT License"
}
JSON

# Create a resolved report where any "UNKNOWN" licenses are replaced from the map
# Also filter out the project itself (dev-agents)
jq --slurpfile map "$PROJECT_ROOT/licenses_map.json" \
  'map( if .License == "UNKNOWN" and $map[0][.Name]
        then .License = $map[0][.Name]
        else .
        end ) | map(select(.Name != "dev-agents"))' \
  "$PROJECT_ROOT/licenses_report.json" > "$PROJECT_ROOT/licenses_report_resolved.json"

REPORT_JSON="$PROJECT_ROOT/licenses_report_resolved.json"

# Analyze licenses for AGPL compliance
echo "🔍 Analyzing license compatibility..."

# Known compatible licenses with AGPL v3
COMPATIBLE_LICENSES=(
    "MIT License"
    "BSD License"
    "BSD 3-Clause License"
    "Apache Software License"
    "Apache License 2.0"
    "Python Software Foundation License"
    "The Unlicense (Unlicense)"
    "Apache-2.0 AND MIT"
    "Apache Software License; BSD License"
    "Apache Software License; MIT License"
    "HPND"
)

# Potentially problematic licenses
PROBLEMATIC_LICENSES=(
    "GNU General Public License"
    "GNU Lesser General Public License"
    "Mozilla Public License 2.0 (MPL 2.0)"
)

# Check for unknown licenses (after mapping)
UNKNOWN_COUNT=$(grep -c '"UNKNOWN"' "$REPORT_JSON" || true)
TOTAL_COUNT=$(jq length "$REPORT_JSON")

echo -e "\n📊 License Analysis Results:"
echo -e "Total dependencies: ${TOTAL_COUNT}"
echo -e "Unknown licenses (after mapping): ${UNKNOWN_COUNT}"

if [ "$UNKNOWN_COUNT" -gt 0 ]; then
    echo -e "\n${YELLOW}⚠️  Dependencies with unknown licenses:${NC}"
    jq -r '.[] | select(.License == "UNKNOWN") | "- \(.Name) \(.Version)"' "$REPORT_JSON"
    echo -e "\n${YELLOW}Action required: Manually investigate these dependencies${NC}"
fi

# Check for GPL licenses (incompatible with commercial licensing)
GPL_COUNT=$(jq '[.[] | select(.License | contains("GNU General Public License") and (contains("GNU Affero") | not))] | length' "$REPORT_JSON")

if [ "$GPL_COUNT" -gt 0 ]; then
    echo -e "\n${RED}❌ GPL-licensed dependencies found (incompatible with commercial licensing):${NC}"
    jq -r '.[] | select(.License | contains("GNU General Public License") and (contains("GNU Affero") | not)) | "- \(.Name) \(.Version) (\(.License))"' "$REPORT_JSON"
    exit 1
fi

# Check for MPL licenses - separate known-compatible from others
KNOWN_COMPATIBLE_MPL=("certifi" "tqdm" "pathspec" "pytest-metadata")
MPL_DEPS=$(jq -r '.[] | select(.License | contains("Mozilla Public License")) | .Name' "$REPORT_JSON")
UNKNOWN_MPL_DEPS=()
KNOWN_MPL_DEPS=()

if [ -n "$MPL_DEPS" ]; then
    while IFS= read -r dep; do
        if [[ " ${KNOWN_COMPATIBLE_MPL[*]} " =~ " ${dep} " ]]; then
            KNOWN_MPL_DEPS+=("$dep")
        else
            UNKNOWN_MPL_DEPS+=("$dep")
        fi
    done <<< "$MPL_DEPS"
fi

# Show info for known-compatible MPL dependencies
if [ ${#KNOWN_MPL_DEPS[@]} -gt 0 ]; then
    echo -e "\nℹ️  MPL-licensed dependencies (verified compatible):"
    for dep in "${KNOWN_MPL_DEPS[@]}"; do
        jq -r ".[] | select(.Name == \"$dep\" and (.License | contains(\"Mozilla Public License\"))) | \"- \(.Name) \(.Version) (\(.License))\"" "$REPORT_JSON"
    done
    echo -e "   ${GREEN}✓ These dependencies are compatible with dual AGPL/proprietary licensing${NC}"
    echo -e "   ${GREEN}✓ Do not modify these libraries directly in this project${NC}"
fi

# Warn about unknown MPL dependencies
if [ ${#UNKNOWN_MPL_DEPS[@]} -gt 0 ]; then
    echo -e "\n${YELLOW}⚠️  Unknown MPL-licensed dependencies found (need review):${NC}"
    for dep in "${UNKNOWN_MPL_DEPS[@]}"; do
        jq -r ".[] | select(.Name == \"$dep\" and (.License | contains(\"Mozilla Public License\"))) | \"- \(.Name) \(.Version) (\(.License))\"" "$REPORT_JSON"
    done
    echo -e "${YELLOW}Note: Review these MPL dependencies for licensing compatibility${NC}"
fi

# Summary
echo -e "\n${GREEN}✅ License compliance check completed${NC}"

if [ "$UNKNOWN_COUNT" -eq 0 ] && [ "$GPL_COUNT" -eq 0 ]; then
    echo -e "${GREEN}✅ No blocking license issues found${NC}"
    exit 0
else
    echo -e "${YELLOW}⚠️  Manual review required for unknown licenses${NC}"
    exit 0
fi
