#!/bin/bash
echo "=== Seller Master System Installer ==="
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
mkdir -p database uploads
python app.py &
sleep 2
echo ""
echo "Running at http://localhost:5000"
echo "Login: admin / Admin@123"
