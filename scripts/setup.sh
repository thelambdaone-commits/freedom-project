#!/usr/bin/env bash
set -e

echo "================================================"
echo "  Telegram FreeDomain Bot - Setup"
echo "================================================"
echo ""

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

echo "[1/6] Creating Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

echo "[2/6] Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "[3/6] Installing Scrapling browsers..."
scrapling install 2>/dev/null || python3 -c "from scrapling.cli import install; install([], standalone_mode=False)" 2>/dev/null || echo "  (browsers will install on first run)"

echo "[4/6] Setting up key-hunter..."
if [ ! -d "key-hunter" ]; then
    echo "  Cloning key-hunter..."
    git clone https://github.com/thelambdaone-commits/key-hunter.git
    cd key-hunter
    pip install -r requirements.txt 2>/dev/null || true
    cd "$PROJECT_DIR"
else
    echo "  key-hunter already exists"
fi

echo "[5/6] Creating .env from template..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "  .env created. Edit it with your tokens."
else
    echo "  .env already exists"
fi

echo "[6/6] Generating Fernet key if needed..."
if ! grep -q "FERNET_KEY=" .env || [ "$(grep 'FERNET_KEY=' .env | cut -d= -f2)" = "" ]; then
    FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/FERNET_KEY=/FERNET_KEY=$FERNET_KEY/" .env 2>/dev/null || true
    else
        sed -i "s/FERNET_KEY=/FERNET_KEY=$FERNET_KEY/" .env 2>/dev/null || true
    fi
    echo "  Fernet key generated."
fi

echo ""
echo "================================================"
echo "  Setup complete!"
echo "================================================"
echo ""
echo "Next steps:"
echo "  1. Edit .env with your tokens"
echo "  2. Activate venv: source .venv/bin/activate"
echo "  3. Run: python -m bot.main"
echo ""
echo "Optional:"
echo "  - Install Ollama: curl -fsSL https://ollama.com/install.sh | sh"
echo "  - Pull models: ollama pull llama3"
echo ""
