#!/bin/bash
# Setup script for GitHub Contribution Graph Steganography

echo "Setting up GitHub Contribution Graph Steganography..."

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not installed."
    exit 1
fi

echo "✓ Python 3 found"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

echo "✓ Dependencies installed"

# Install pre-commit hooks (optional)
read -p "Do you want to install pre-commit hooks? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    pip install pre-commit
    pre-commit install
    echo "✓ Pre-commit hooks installed"
fi

# Create config.json from example if it doesn't exist
if [ ! -f "config.json" ] && [ -f "config.json.example" ]; then
    read -p "Do you want to create config.json from example? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cp config.json.example config.json
        echo "✓ Created config.json (edit it with your settings)"
    fi
fi

echo ""
echo "Setup complete!"
echo ""
echo "To get started:"
echo "  1. Activate the virtual environment: source venv/bin/activate"
echo "  2. (Optional) Add your GitHub token to token.txt"
echo "  3. (Optional) Edit config.json with your preferences"
echo "  4. Run encoder: python encoder.py \"Your message\" --start 2024-01-01 --dry-run"
echo "  5. Run tests: python -m unittest discover"
echo ""
