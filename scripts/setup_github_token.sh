#!/bin/bash
set -e

echo "=================================="
echo "GitHub Token Setup for Cloud Agent"
echo "=================================="
echo ""

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo "❌ Error: GitHub CLI (gh) is not installed"
    echo ""
    echo "Install with:"
    echo "  brew install gh        # macOS"
    echo "  or visit: https://cli.github.com/"
    exit 1
fi

echo "✓ GitHub CLI found"
echo ""

# Check if already authenticated
if ! gh auth status &> /dev/null; then
    echo "You need to authenticate with GitHub first."
    echo "Running: gh auth login"
    echo ""
    gh auth login
    echo ""
fi

echo "✓ GitHub authentication verified"
echo ""

# Create a token with appropriate scopes
echo "Creating a GitHub token with required scopes..."
echo "Scopes: repo (full control), read:org"
echo ""

TOKEN=$(gh auth token)

if [ -z "$TOKEN" ]; then
    echo "❌ Failed to get token from gh auth token"
    echo ""
    echo "Alternative: Create a token manually"
    echo "1. Visit: https://github.com/settings/tokens/new"
    echo "2. Add scopes: repo, read:org"
    echo "3. Copy the token and run:"
    echo "   echo 'SYSTEM_GITHUB_TOKEN=your-token-here' >> .env"
    exit 1
fi

# Add to .env file
ENV_FILE=".env"

# Check if SYSTEM_GITHUB_TOKEN already exists in .env
if grep -q "^SYSTEM_GITHUB_TOKEN=" "$ENV_FILE" 2>/dev/null; then
    # Update existing line (without displaying the token)
    sed -i.bak "s|^SYSTEM_GITHUB_TOKEN=.*|SYSTEM_GITHUB_TOKEN=$TOKEN|" "$ENV_FILE"
    rm -f "$ENV_FILE.bak"
    echo "✓ Updated SYSTEM_GITHUB_TOKEN in $ENV_FILE"
else
    # Append new line
    echo "SYSTEM_GITHUB_TOKEN=$TOKEN" >> "$ENV_FILE"
    echo "✓ Added SYSTEM_GITHUB_TOKEN to $ENV_FILE"
fi

echo ""
echo "=================================="
echo "✅ GitHub token configured!"
echo "=================================="
echo ""
echo "Next steps:"
echo "1. Add your Anthropic API key to .env:"
echo "   SYSTEM_ANTHROPIC_API_KEY=sk-ant-..."
echo ""
echo "2. Add your Novita API key to .env:"
echo "   NOVITA_API_KEY=your-novita-key"
echo ""
echo "3. Run the test:"
echo "   python scripts/test_novita_claude_code.py"
echo ""
