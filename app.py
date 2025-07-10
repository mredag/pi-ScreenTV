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
VIDEO_DIR = os.path.join(BASE_DIR, 'videos')

# Log dizinini oluştur
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)

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
        self.automation_paused = False
        self.config = self.load_config()

        self.videos = self.get_video_files()
        
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
                "cameras": [{"name": "Kamera 1", "url": "rtsp://192.168.1.100:554/stream1"}],
                "mpv_options": ["--fullscreen", "--no-osc", "--no-input-default-bindings"],
                "startup_delay": 5
            }

    def save_config(self):
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
            logger.info("Yapılandırma kaydedildi")
            return True
        except Exception as e:
            logger.error(f"Yapılandırma kaydedilemedi: {e}")
            return False

    def get_video_files(self):
        try:
            return [f for f in os.listdir(VIDEO_DIR) if f.lower().endswith('.mp4')]
        except FileNotFoundError:
            return []
    
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
    
    def play_video(self, video_list=None):
        """Video oynat"""
        self.videos = self.get_video_files()
        if not video_list:
            if not self.videos:
                logger.error("Video listesi boş")
                return False, "Video bulunamadı"
            video_paths = [os.path.join(VIDEO_DIR, self.videos[0])]
        else:
            # Gelen deger tek bir dosya adi ise listeye cevir
            if isinstance(video_list, str):
                video_list = [video_list]
            video_paths = [os.path.join(VIDEO_DIR, v) for v in video_list]

        for path in video_paths:
            if not os.path.exists(path):
                logger.error(f"Video dosyası bulunamadı: {path}")
                return False, "Video dosyası bulunamadı"
        
        # Mevcut oynatmayı durdur ve otomasyonu duraklat
        self.stop_current()
        self.pause_automation()
        
        with self.lock:
            try:
                # MPV komutunu oluştur
                cmd = ['mpv'] + self.config.get('mpv_options', []) + ['--input-ipc-server=/tmp/mpvsocket', '--loop=playlist'] + video_paths
                
                # İşlemi başlat
                self.current_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                self.current_source = 'video'
                logger.info(f"Video oynatılıyor: {video_paths}")
                return True, "Video oynatma başlatıldı"
                
            except Exception as e:
                logger.error(f"Video oynatma hatası: {e}")
                return False, f"Hata: {str(e)}"
    
    def play_camera(self, name=None):
        """Kamera yayınını göster"""
        cameras = self.config.get('cameras', [])
        camera_url = None
        if name:
            for cam in cameras:
                if cam.get('name') == name:
                    camera_url = cam.get('url')
                    break
        if not camera_url and cameras:
            camera_url = cameras[0].get('url')
        if not camera_url:
            logger.error("Kamera URL'si yapılandırılmamış")
            return False, "Kamera yapılandırması eksik"
        
        # Mevcut oynatmayı durdur ve otomasyonu duraklat
        self.stop_current()
        self.pause_automation()
        
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
                    'status': f"{self.current_source.capitalize()} oynatılıyor",
                    'automation_paused': self.automation_paused
                }
            else:
                return {
                    'playing': False,
                    'source': None,
                    'status': 'Beklemede',
                    'automation_paused': self.automation_paused
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
        if self.automation_paused:
            return
        if rule.get("source") == "camera":
            self.play_camera(rule.get("camera"))
        elif rule.get("source") == "video":
            video = rule.get("video")
            self.play_video([video] if video else None)

    def play_default(self):
        if self.automation_paused:
            return
        if self.current_source != "video":
            self.play_video()

    def add_camera(self, name, url):
        cams = self.config.setdefault('cameras', [])
        cams.append({'name': name, 'url': url})
        self.save_config()

    def remove_camera(self, name):
        cams = self.config.get('cameras', [])
        self.config['cameras'] = [c for c in cams if c.get('name') != name]
        self.save_config()

    def pause_automation(self):
        self.automation_paused = True

    def resume_automation(self):
        self.automation_paused = False


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

@app.route('/videos')
def videos():
    return jsonify({'videos': player.get_video_files()})

@app.route('/play_video', methods=['POST'])
def play_video():
    """Video oynatma endpoint'i"""
    logger.info("Video oynatma isteği alındı")
    data = request.get_json(silent=True) or {}
    videos = data.get('videos')
    success, message = player.play_video(videos)
    
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


@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('file')
    if not file:
        return jsonify({'success': False, 'message': 'Dosya bulunamadı'})
    path = os.path.join(VIDEO_DIR, file.filename)
    file.save(path)
    return jsonify({'success': True})


@app.route('/cameras', methods=['GET', 'POST', 'DELETE'])
def cameras():
    if request.method == 'GET':
        return jsonify({'cameras': player.config.get('cameras', [])})
    data = request.get_json(force=True)
    name = data.get('name')
    if request.method == 'POST':
        url = data.get('url')
        player.add_camera(name, url)
    elif request.method == 'DELETE':
        player.remove_camera(name)
    return jsonify({'success': True})


@app.route('/resume', methods=['POST'])
def resume():
    player.resume_automation()
    return jsonify({'success': True})


@app.route('/system_info')
def system_info():
    temp = ''
    try:
        out = subprocess.check_output(['vcgencmd', 'measure_temp']).decode()
        temp = out.strip().split('=')[1]
    except Exception:
        temp = 'N/A'
    disk = subprocess.check_output(['df', '-h', '/']).decode().splitlines()[1].split()[4]
    return jsonify({'temperature': temp, 'disk_usage': disk})


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