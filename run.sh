#!/bin/bash

# Set up virtual environment and install backend dependencies
echo "[*] Setting up backend virtual environment..."
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run backend server in the background
echo "[*] Starting backend server..."
uvicorn main:app --host 0.0.0.0 --port 8000 &

# Return to root directory
cd ..

# Start Vault in dev mode with log redirection
echo "[*] Starting Vault in dev mode..."
vault server -dev -log-level=debug > vault.log 2>&1 &
VAULT_PID=$!

# Open frontend in default browser
echo "[*] Opening frontend in default browser..."
xdg-open frontend/index.html || open frontend/index.html || start frontend/index.html

# Wait for the user to terminate
echo "[*] Press Ctrl+C to stop everything..."
wait $VAULT_PID

