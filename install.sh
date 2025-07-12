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
# Nginx'i bağımlılıklara ekliyoruz
sudo apt install -y python3 python3-venv python3-pip mpv git nginx # <-- DEĞİŞTİRİLDİ

step "3. Setting up Python virtual environment"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

step "4. Creating required directories"
mkdir -p videos logs static/images # <-- 'static/images' eklendi

if [ -f logo.png ]; then
  step "Setting desktop wallpaper"
  pcmanfm --set-wallpaper "$BASE_DIR/logo.png" || true
fi

step "5. Verifying MPV installation"
if ! command -v mpv >/dev/null; then
  echo -e "${RED}mpv could not be found. Please check the package installation.${NC}"
  exit 1
fi

# <-- YENİ BÖLÜM BAŞLANGICI -->
step "6. Configuring network access for easy use"
step "   - Setting hostname to 'eformtv'"
sudo hostnamectl set-hostname eformtv

step "   - Configuring Nginx as a reverse proxy (port 80 -> 5000)"
# /etc/nginx/sites-available/default dosyasını aşağıdaki içerikle yeniden yazıyoruz
sudo tee /etc/nginx/sites-available/default > /dev/null <<'EOF'
server {
    listen 80;
    server_name eformtv.local;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

step "   - Enabling and restarting Nginx service"
sudo systemctl enable nginx
sudo systemctl restart nginx
# <-- YENİ BÖLÜM SONU -->

step "7. Copying systemd service" # <-- Adım numarası güncellendi
sudo cp pi-ekran.service /etc/systemd/system/pi-ekran.service
sudo systemctl daemon-reload
sudo systemctl enable pi-ekran.service

step "8. Running basic tests" # <-- Adım numarası güncellendi
python3 -m py_compile app.py

step "9. Starting the main application service" # <-- Adım numarası güncellendi
sudo systemctl restart pi-ekran.service
sleep 2
sudo systemctl status pi-ekran.service --no-pager || true

# IP adresini bulmaya artık gerek yok, sabit bir domain kullanıyoruz.
echo -e "${GREEN}Installation complete. Access the web interface at: http://eformtv.local${NC}" # <-- DEĞİŞTİRİLDİ