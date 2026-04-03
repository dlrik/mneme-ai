#!/usr/bin/env bash
# install.sh — Install mneme-ai

set -e

echo "Installing mneme-ai..."

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python: $PYTHON_VERSION"

# Create config directory
CONFIG_DIR="$HOME/.config/mneme"
mkdir -p "$CONFIG_DIR"

# Create default config if it doesn't exist
if [ ! -f "$CONFIG_DIR/config.json" ]; then
    cat > "$CONFIG_DIR/config.json" << 'EOF'
{
  "env": {
    "VOYAGE_API_KEY": ""
  }
}
EOF
    echo "Created config at $CONFIG_DIR/config.json"
    echo "Edit it and add your VOYAGE_API_KEY"
else
    echo "Config already exists at $CONFIG_DIR/config.json"
fi

# Install package
echo "Installing Python package..."
pip install -e .

# Create data directory
DATA_DIR="$HOME/.local/share/mneme"
mkdir -p "$DATA_DIR"
echo "Data directory: $DATA_DIR"

echo ""
echo "Done! To start:"
echo "  mneme-server        # Start the web server"
echo "  python -m mneme_mcp.server  # Start MCP server"
echo ""
echo "Edit $CONFIG_DIR/config.json to add your VOYAGE_API_KEY"
