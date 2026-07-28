#!/bin/bash
# install.sh — Install gem-pw and dependencies
set -e

echo "=== gem-pw installer ==="

# Install Python dependencies
echo "Installing Python deps..."
pip install playwright aiohttp 2>&1 | tail -1

# Install Chromium
echo "Installing Chromium..."
playwright install chromium 2>&1 | tail -1

# Install scripts
BIN_DIR="${HOME}/.local/bin"
mkdir -p "$BIN_DIR"

cp gem-pw "$BIN_DIR/gem-pw"
cp gem-pw-login "$BIN_DIR/gem-pw-login"
cp gemini-web "$BIN_DIR/gemini-web"
cp apply_gem_diff.py "$BIN_DIR/apply_gem_diff.py"
chmod +x "$BIN_DIR/gem-pw" "$BIN_DIR/gem-pw-login" "$BIN_DIR/gemini-web" "$BIN_DIR/apply_gem_diff.py"

echo ""
echo "=== Installed ==="
echo "  gem-pw            → $BIN_DIR/gem-pw"
echo "  gem-pw-login      → $BIN_DIR/gem-pw-login"
echo "  gemini-web        → $BIN_DIR/gemini-web"
echo "  apply_gem_diff.py → $BIN_DIR/apply_gem_diff.py"
echo ""
echo "=== Next Steps ==="
echo "  1. Run: gem-pw-login"
echo "  2. Sign into Gemini in the Chromium window"
echo "  3. Use: gem-pw <gem-id> 'prompt'"
