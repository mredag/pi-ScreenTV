#!/usr/bin/env python3
"""
Pi-Ekran: Raspberry Pi Tabanlı Dijital Tabela Sistemi
Ana Flask uygulaması - Video ve kamera yayını kontrolcüsü
"""

import os
import json
import subprocess
import time
import logging
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from threading import Lock
from apscheduler.schedulers.background import BackgroundScheduler
import signal

# Uygulama dizini
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')
LOG_DIR = os.path.join(BASE_DIR, 'logs')

# Log dizinini oluştur
os.makedirs(LOG_DIR, exist_ok=True)

# Logging yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, f'pi-ekran_{datetime.now().strftime("%Y%m%d")}.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('PiEkran')

# Flask uygulaması
app = Flask(__name__)

class MediaPlayer:
    """MPV media player kontrolcüsü"""
    
    def __init__(self):
        self.current_process = None
        self.current_source = None
        self.lock = Lock()
        self.config = self.load_config()
        
        self.scheduler = BackgroundScheduler(timezone="Europe/Istanbul")
        self.start_scheduler()
    def load_config(self):
        """Yapılandırma dosyasını yükle"""
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                logger.info("Yapılandırma dosyası yüklendi")
                return config
        except Exception as e:
            logger.error(f"Yapılandırma dosyası yüklenemedi: {e}")
            # Varsayılan yapılandırma
            return {
                "default_video": os.path.join(BASE_DIR, "videos", "tanitim.mp4"),
                "camera_url": "rtsp://192.168.1.100:554/stream1",
                "mpv_options": ["--fullscreen", "--no-osc", "--no-input-default-bindings"],
                "startup_delay": 5
            }
    
    def stop_current(self):
        """Mevcut oynatmayı durdur"""
        with self.lock:
            if self.current_process:
                try:
                    # Önce kibarca durdur
                    self.current_process.terminate()
                    time.sleep(1)
                    
                    # Hala çalışıyorsa zorla kapat
                    if self.current_process.poll() is None:
                        self.current_process.kill()
                        logger.warning("İşlem zorla kapatıldı")
                    
                    self.current_process = None
                    self.current_source = None
                    logger.info("Mevcut oynatma durduruldu")
                    return True
                except Exception as e:
                    logger.error(f"Oynatma durdurulurken hata: {e}")
                    return False
            return True
    
    def play_video(self, video_path=None):
        """Video oynat"""
        if video_path is None:
            video_path = self.config.get('default_video')
        
        # Dosya kontrolü
        if not os.path.exists(video_path):
            logger.error(f"Video dosyası bulunamadı: {video_path}")
            return False, "Video dosyası bulunamadı"
        
        # Mevcut oynatmayı durdur
        self.stop_current()
        
        with self.lock:
            try:
                # MPV komutunu oluştur
                cmd = ['mpv'] + self.config.get('mpv_options', []) + ['--input-ipc-server=/tmp/mpvsocket', '--loop=inf', video_path]
                
                # İşlemi başlat
                self.current_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                self.current_source = 'video'
                logger.info(f"Video oynatılıyor: {video_path}")
                return True, "Video oynatma başlatıldı"
                
            except Exception as e:
                logger.error(f"Video oynatma hatası: {e}")
                return False, f"Hata: {str(e)}"
    
    def play_camera(self):
        """Kamera yayınını göster"""
        camera_url = self.config.get('camera_url')
        
        if not camera_url:
            logger.error("Kamera URL'si yapılandırılmamış")
            return False, "Kamera yapılandırması eksik"
        
        # Mevcut oynatmayı durdur
        self.stop_current()
        
        with self.lock:
            try:
                # MPV komutunu oluştur
                cmd = ['mpv'] + self.config.get('mpv_options', []) + ['--input-ipc-server=/tmp/mpvsocket', camera_url]
                
                # İşlemi başlat
                self.current_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                self.current_source = 'camera'
                logger.info(f"Kamera yayını başlatıldı: {camera_url}")
                return True, "Kamera yayını başlatıldı"
                
            except Exception as e:
                logger.error(f"Kamera yayını hatası: {e}")
                return False, f"Hata: {str(e)}"
    
    def get_status(self):
        """Mevcut durumu getir"""
        with self.lock:
            if self.current_process and self.current_process.poll() is None:
                return {
                    'playing': True,
                    'source': self.current_source,
                    'status': f"{self.current_source.capitalize()} oynatılıyor"
                }
            else:
                return {
                    'playing': False,
                    'source': None,
                    'status': 'Beklemede'
                }
    def start_scheduler(self):
        for rule in self.config.get("schedule", []):
            days = [d.lower()[:3] for d in rule.get("days", [])]
            start_h, start_m = map(int, rule.get("start", "0:0").split(":"))
            end_h, end_m = map(int, rule.get("end", "0:0").split(":"))

            self.scheduler.add_job(
                self.apply_schedule_rule,
                "cron",
                day_of_week=",".join(days),
                hour=start_h,
                minute=start_m,
                args=[rule],
            )

            self.scheduler.add_job(
                self.play_default,
                "cron",
                day_of_week=",".join(days),
                hour=end_h,
                minute=end_m,
            )

        self.scheduler.start()

    def apply_schedule_rule(self, rule):
        if rule.get("source") == "camera":
            self.play_camera()
        elif rule.get("source") == "video":
            self.play_video(rule.get("video"))

    def play_default(self):
        if self.current_source != "video":
            self.play_video()


    def show_announcement(self, text, duration=10):
        socket_path = "/tmp/mpvsocket"
        if not os.path.exists(socket_path):
            logger.error("MPV soketi bulunamadı")
            return False, "Oynatıcı hazır değil"
        try:
            import socket as s
            client = s.socket(s.AF_UNIX, s.SOCK_STREAM)
            client.connect(socket_path)
            cmd = {"command": ["show-text", text, duration * 1000]}
            client.send((json.dumps(cmd) + "\n").encode("utf-8"))
            client.close()
            logger.info("Duyuru gösterildi")
            return True, "Duyuru gösterildi"
        except Exception as e:
            logger.error(f"Duyuru hatası: {e}")
            return False, str(e)

# Global media player instance
player = MediaPlayer()

@app.route('/')
def index():
    """Ana sayfa"""
    return render_template('index.html')

@app.route('/status')
def status():
    """Sistem durumu"""
    return jsonify(player.get_status())

@app.route('/play_video', methods=['POST'])
def play_video():
    """Video oynatma endpoint'i"""
    logger.info("Video oynatma isteği alındı")
    success, message = player.play_video()
    
    return jsonify({
        'success': success,
        'message': message,
        'status': player.get_status()
    })

@app.route('/play_camera', methods=['POST'])
def play_camera():
    """Kamera yayını endpoint'i"""
    logger.info("Kamera yayını isteği alındı")
    success, message = player.play_camera()
    
    return jsonify({
        'success': success,
        'message': message,
        'status': player.get_status()
    })

@app.route('/stop', methods=['POST'])
def stop():
    """Oynatmayı durdur"""
    logger.info("Durdurma isteği alındı")
    success = player.stop_current()
    
    return jsonify({
        'success': success,
        'message': 'Oynatma durduruldu' if success else 'Hata oluştu',
        'status': player.get_status()
    })
@app.route('/announce', methods=['POST'])
def announce():
    data = request.get_json(force=True)
    message = data.get('message', '') if data else ''
    logger.info('Duyuru istegi alindi')
    success, msg = player.show_announcement(message)
    return jsonify({'success': success, 'message': msg})


def startup_sequence():
    """Başlangıç dizisi - fallback mantığı"""
    logger.info("Pi-Ekran başlatılıyor...")
    
    # Yapılandırmada belirtilen süre kadar bekle
    delay = player.config.get('startup_delay', 5)
    logger.info(f"{delay} saniye bekleniyor...")
    time.sleep(delay)
    
    # Varsayılan videoyu oynat
    try:
        success, message = player.play_video()
        if success:
            logger.info("Başlangıç videosu oynatılıyor")
        else:
            logger.error(f"Başlangıç videosu oynatılamadı: {message}")
    except Exception as e:
        logger.error(f"Başlangıç hatası: {e}")

def signal_handler(sig, frame):
    """Graceful shutdown"""
    logger.info("Kapatma sinyali alındı")
    try:
        player.scheduler.shutdown()
    except Exception:
        pass
    player.stop_current()
    exit(0)

if __name__ == '__main__':
    # Signal handler'ı ayarla
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Başlangıç dizisini çalıştır
    startup_sequence()
    
    # Flask uygulamasını başlat
    logger.info("Web sunucusu başlatılıyor...")
    app.run(host='0.0.0.0', port=player.config.get('web_port', 5000), debug=False)