#!/bin/bash
# Pi-Ekran Otomatik Kurulum Scripti

set -e  # Hata durumunda çık

echo "================================================"
echo "Pi-Ekran Kurulum Scripti v2.0"
echo "================================================"

# Renk kodları
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Root kontrolü
if [[ $EUID -eq 0 ]]; then
   echo -e "${RED}Bu script root olarak çalıştırılmamalı!${NC}"
   exit 1
fi

# Ana dizin
BASE_DIR="/home/pi/pi-ekran"

echo -e "${YELLOW}1. Sistem güncellemeleri yapılıyor...${NC}"
sudo apt update && sudo apt upgrade -y

echo -e "${YELLOW}2. Gerekli paketler yükleniyor...${NC}"
sudo apt install -y python3-pip python3-venv mpv git

echo -e "${YELLOW}3. Proje dizini oluşturuluyor...${NC}"
mkdir -p $BASE_DIR/{static,templates,videos,logs}
cd $BASE_DIR

echo -e "${YELLOW}4. Python sanal ortamı oluşturuluyor...${NC}"
python3 -m venv venv
source venv/bin/activate
pip install flask

echo -e "${YELLOW}5. Test videosu indiriliyor...${NC}"
wget -q https://sample-videos.com/video321/mp4/720/big_buck_bunny_720p_1mb.mp4 -O videos/tanitim.mp4

echo -e "${YELLOW}6. Yapılandırma dosyaları oluşturuluyor...${NC}"

# app.py dosyasını kontrol et
if [ ! -f "app.py" ]; then
    echo -e "${RED}app.py dosyası bulunamadı! Lütfen dosyaları kopyalayın.${NC}"
    exit 1
fi

echo -e "${YELLOW}7. Systemd servisi yapılandırılıyor...${NC}"
sudo cp pi-ekran.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable pi-ekran.service

echo -e "${YELLOW}8. GPU belleği artırılıyor (opsiyonel)...${NC}"
if ! grep -q "gpu_mem=128" /boot/config.txt; then
    echo "gpu_mem=128" | sudo tee -a /boot/config.txt
fi

echo -e "${YELLOW}9. Ses çıkışı HDMI olarak ayarlanıyor...${NC}"
sudo raspi-config nonint do_audio 2

echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}Kurulum tamamlandı!${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""
echo "Yapılması gerekenler:"
echo "1. config.json dosyasındaki camera_url'yi düzenleyin"
echo "2. Sistemi yeniden başlatın: sudo reboot"
echo "3. Web arayüzüne erişin: http://$(hostname -I | awk '{print $1}'):5000"
echo ""
echo "Servis kontrolü için:"
echo "  sudo systemctl status pi-ekran.service"
echo "  sudo journalctl -u pi-ekran.service -f"
echo ""
echo -e "${YELLOW}Sistem yeniden başlatılsın mı? (e/h)${NC}"
read -r response
if [[ "$response" =~ ^([eE][vV][eE][tT]|[eE])$ ]]; then
    sudo reboot
fi