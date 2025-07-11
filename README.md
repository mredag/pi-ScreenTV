# Pi-Ekran Kurulum ve Yapılandırma Kılavuzu

## Hızlı Kurulum (GitHub)

GitHub deposunu kullanarak uygulamayı birkaç komutla kurabilirsiniz. `pi` kullanıcısı ile oturum açtıktan sonra aşağıdaki adımları izleyin:

```bash
sudo apt update && sudo apt install -y git
git clone https://github.com/mredag/pi-ScreenTV.git ~/pi-ekran
cd ~/pi-ekran
bash install.sh
```

Kurulum tamamlandığında servis etkinleşir ve web arayüzüne `http://pi-ekran.local:5000` adresinden erişebilirsiniz.
Yeni yan menülü gösterge panelini kullanmak için `http://pi-ekran.local:5000/dashboard` adresine gidin.

### Güncelleme

Mevcut kurulumunuzu güncellemek için aynı dizinde aşağıdaki komutları çalıştırmanız yeterlidir:

```bash
cd ~/pi-ekran
git pull
bash install.sh
sudo systemctl restart pi-ekran.service
```

## Faz 0: Donanım ve Sistem Hazırlığı

### 1. Donanım Gereksinimleri
- Raspberry Pi 4 veya 5 (4GB+ RAM önerilir)
- Harici USB 3.0 SSD (120GB+ önerilir)
- HDMI kablo ve ekran
- Güç adaptörü (Pi 4 için 3A, Pi 5 için 5A)
- Ethernet kablosu (opsiyonel ama önerilir)

### 2. Raspberry Pi OS Kurulumu

1. **Raspberry Pi Imager'ı indirin**
   - https://www.raspberrypi.com/software/

2. **SSD'ye OS kurulumu**
   - Raspberry Pi OS (64-bit) seçin
   - Storage olarak USB SSD'yi seçin
   - Advanced options'a tıklayın:
     - Hostname: `pi-ekran`
     - SSH'ı etkinleştirin
     - Kullanıcı adı: `pi`
     - Wifi bilgilerini girin (varsa)

3. **İlk Başlatma**
   - SSD'yi Pi'ye bağlayın
   - HDMI ve güç kablosunu bağlayın
   - Sistem açılana kadar bekleyin

### 3. Temel Sistem Yapılandırması

SSH ile bağlanın:
```bash
ssh pi@pi-ekran.local
```

Sistemi güncelleyin:
```bash
sudo apt update && sudo apt upgrade -y
```

Gerekli paketleri yükleyin:
```bash
sudo apt install -y python3-pip python3-venv mpv git
```

### 4. Proje Dizinini Oluşturma

```bash
mkdir ~/pi-ekran
cd ~/pi-ekran
```

### 5. Python Sanal Ortamı

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 6. Test Video ve Kamera Kontrolü

Test videosu indirin:
```bash
wget https://sample-videos.com/video321/mp4/720/big_buck_bunny_720p_1mb.mp4 -O test_video.mp4
```

Video testi:
```bash
mpv test_video.mp4
```

Kamera testi (varsa):
```bash
mpv rtsp://192.168.1.100:554/stream1
```

## Faz 1: Çekirdek MVP Geliştirmesi

### 1. Proje Dosya Yapısı

```
/home/pi/pi-ekran/
├── app.py              # Ana Flask uygulaması
├── config.json         # Yapılandırma dosyası
├── static/
│   ├── style.css      # CSS dosyası
│   └── script.js      # JavaScript dosyası
├── templates/
│   └── index.html     # Ana web arayüzü
├── videos/            # Video dosyaları için dizin
│   └── tanitim.mp4   # Varsayılan tanıtım videosu
├── logs/              # Log dosyaları için dizin
└── venv/              # Python sanal ortamı
```

### 2. Dosyaları Oluşturma

Gerekli dizinleri oluşturun:
```bash
mkdir -p ~/pi-ekran/{static,templates,videos,logs}
```

Ardından aşağıdaki kod dosyalarını oluşturun:
- app.py
- config.json
- templates/index.html
- static/style.css
- static/script.js

### 3. Test Etme

Uygulamayı çalıştırın:
```bash
cd ~/pi-ekran
source venv/bin/activate
python3 app.py
```

Web tarayıcıda açın:
```
http://pi-ekran.local:5000
```

## Faz 2: Otomasyon ve Güvenilirlik

### 1. Systemd Servisi Oluşturma

Service dosyası oluşturun:
```bash
sudo nano /etc/systemd/system/pi-ekran.service
```

İçeriği yapıştırın (aşağıdaki kod dosyalarında verilmiştir).

### 2. Servisi Etkinleştirme

```bash
sudo systemctl daemon-reload
sudo systemctl enable pi-ekran.service
sudo systemctl start pi-ekran.service
```

Durum kontrolü:
```bash
sudo systemctl status pi-ekran.service
```

### 3. Log Kontrolü

```bash
journalctl -u pi-ekran.service -f
```

### 4. Dayanıklılık Testi

Pi'yi yeniden başlatın:
```bash
sudo reboot
```

Sistem açıldıktan sonra web arayüzünün otomatik olarak erişilebilir olduğunu kontrol edin.

## Sorun Giderme

### MPV Sorunları
- Ses çıkışı yoksa: `raspi-config` ile ses çıkışını HDMI olarak ayarlayın
- Video takılıyorsa: GPU belleğini artırın (`sudo raspi-config` > Advanced Options)

### Ağ Sorunları
- Statik IP atayın veya router'da DHCP rezervasyonu yapın
- Firewall'da 5000 portunu açın

### Servis Sorunları
- Logları kontrol edin: `journalctl -u pi-ekran.service -n 50`
- Manuel test: `sudo -u pi /home/pi/pi-ekran/venv/bin/python /home/pi/pi-ekran/app.py`
