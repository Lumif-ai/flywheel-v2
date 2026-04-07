#!/usr/bin/env bash
# -----------------------------------------------------------------------
# Publish flywheel-ai CLI package to PyPI
#
# Prerequisites:
#   1. PyPI account at https://pypi.org/account/register/
#   2. API token at https://pypi.org/manage/account/token/
#   3. uv installed (brew install uv)
#
# First-time setup:
#   Create ~/.pypirc:
#     [pypi]
#     username = __token__
#     password = pypi-XXXXXXXXXXXX
#
# Usage:
#   ./scripts/publish-cli.sh          # publish to PyPI
#   ./scripts/publish-cli.sh --test   # publish to Test PyPI first
# -----------------------------------------------------------------------

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CLI_DIR="$SCRIPT_DIR/../cli"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC}   $*"; }
fail()    { echo -e "${RED}[FAIL]${NC} $*"; exit 1; }

# Check prerequisites
command -v uv &>/dev/null || fail "uv not found. Install: brew install uv"

# Parse args
TEST_PYPI=false
if [[ "${1:-}" == "--test" ]]; then
    TEST_PYPI=true
    info "Publishing to Test PyPI"
fi

# Clean previous builds
info "Cleaning previous builds..."
rm -rf "$CLI_DIR/dist" "$CLI_DIR/build" "$CLI_DIR"/*.egg-info

# Build
info "Building package..."
cd "$CLI_DIR"
uv build

# Show what was built
echo ""
ls -lh dist/
echo ""

# Get version from built package
VERSION=$(ls dist/*.tar.gz | sed 's/.*-\([0-9]*\.[0-9]*\.[0-9]*\).*/\1/')
info "Package version: $VERSION"

# Publish
if $TEST_PYPI; then
    info "Uploading to Test PyPI..."
    uv publish --publish-url https://test.pypi.org/legacy/
    echo ""
    success "Published to Test PyPI!"
    echo -e "  View:    ${BOLD}https://test.pypi.org/project/flywheel-ai/${NC}"
    echo -e "  Install: ${BOLD}pip install -i https://test.pypi.org/simple/ flywheel-ai${NC}"
else
    info "Uploading to PyPI..."
    uv publish
    echo ""
    success "Published to PyPI!"
    echo -e "  View:    ${BOLD}https://pypi.org/project/flywheel-ai/${NC}"
    echo -e "  Install: ${BOLD}pip install flywheel-ai${NC}"
fi
