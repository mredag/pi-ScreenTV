#!/usr/bin/env bash
# Automated setup script for Pi-ScreenTV
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

if [ "$(id -u)" = 0 ]; then
  echo -e "${RED}Please run this script as the 'pi' user, not root.${NC}"
  exit 1
fi

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$BASE_DIR"

step() {
  echo -e "${YELLOW}$*${NC}"
}

step "1. Updating system packages"
sudo apt update -y && sudo apt upgrade -y

step "2. Installing dependencies"
sudo apt install -y python3 python3-venv python3-pip mpv git

step "3. Setting up Python virtual environment"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

step "4. Creating required directories"
mkdir -p videos logs

step "5. Verifying MPV installation"
if ! command -v mpv >/dev/null; then
  echo -e "${RED}mpv could not be found. Please check the package installation.${NC}"
  exit 1
fi

step "6. Copying systemd service"
sudo cp pi-ekran.service /etc/systemd/system/pi-ekran.service
sudo systemctl daemon-reload
sudo systemctl enable pi-ekran.service

step "7. Running basic tests"
python3 -m py_compile app.py

step "8. Starting service"
sudo systemctl restart pi-ekran.service
sleep 2
sudo systemctl status pi-ekran.service --no-pager

IP=$(hostname -I | awk '{print $1}')
echo -e "${GREEN}Installation complete. Access the web interface at: http://${IP}:5000${NC}"
