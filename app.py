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
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request
from threading import Lock
from apscheduler.schedulers.background import BackgroundScheduler
import signal
import socket
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from werkzeug.utils import secure_filename
import psutil

# Uygulama dizini
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
LOG_DIR = os.path.join(BASE_DIR, "logs")
VIDEO_DIR = os.path.join(BASE_DIR, "videos")
IMAGE_DIR = os.path.join(BASE_DIR, "static", "images")

# Log dizinini oluştur
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)
os.makedirs(IMAGE_DIR, exist_ok=True)

# Logging yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(
            os.path.join(LOG_DIR, f'pi-ekran_{datetime.now().strftime("%Y%m%d")}.log'),
            encoding="utf-8",
        ),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("PiEkran")

# Flask uygulaması
app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = VIDEO_DIR
app.config["IMAGE_UPLOAD_FOLDER"] = IMAGE_DIR


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
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                logger.info("Yapılandırma dosyası yüklendi")
                return config
        except Exception as e:
            logger.error(f"Yapılandırma dosyası yüklenemedi: {e}")
            # Varsayılan yapılandırma
            return {
                "default_video": os.path.join(BASE_DIR, "videos", "tanitim.mp4"),
                "cameras": [
                    {"name": "Kamera 1", "url": "rtsp://192.168.1.100:554/stream1"}
                ],
                "mpv_options": [
                    "--fullscreen",
                    "--no-osc",
                    "--no-input-default-bindings",
                ],
                "startup_delay": 5,
            }

    def save_config(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
            logger.info("Yapılandırma kaydedildi")
            return True
        except Exception as e:
            logger.error(f"Yapılandırma kaydedilemedi: {e}")
            return False

    def get_video_files(self):
        try:
            return [f for f in os.listdir(VIDEO_DIR) if f.lower().endswith(".mp4")]
        except FileNotFoundError:
            return []

    def get_image_files(self):
        try:
            return [
                f
                for f in os.listdir(IMAGE_DIR)
                if f.lower().endswith((".jpg", ".jpeg", ".png"))
            ]
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
                cmd = (
                    ["mpv"]
                    + self.config.get("mpv_options", [])
                    + ["--input-ipc-server=/tmp/mpvsocket", "--loop-playlist=inf"]
                    + video_paths
                )

                # İşlemi başlat
                self.current_process = subprocess.Popen(
                    cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )

                self.current_source = "video"
                logger.info(f"Video oynatılıyor: {video_paths}")
                return True, "Video oynatma başlatıldı"

            except Exception as e:
                logger.error(f"Video oynatma hatası: {e}")
                return False, f"Hata: {str(e)}"

    def play_camera(self, name=None):
        """Kamera yayınını göster"""
        cameras = self.config.get("cameras", [])
        camera_url = None
        if name:
            for cam in cameras:
                if cam.get("name") == name:
                    camera_url = cam.get("url")
                    break
        if not camera_url and cameras:
            camera_url = cameras[0].get("url")
        if not camera_url:
            logger.error("Kamera URL'si yapılandırılmamış")
            return False, "Kamera yapılandırması eksik"

        # Mevcut oynatmayı durdur ve otomasyonu duraklat
        self.stop_current()
        self.pause_automation()

        with self.lock:
            try:
                # MPV komutunu oluştur
                cmd = (
                    ["mpv"]
                    + self.config.get("mpv_options", [])
                    + ["--input-ipc-server=/tmp/mpvsocket", camera_url]
                )

                # İşlemi başlat
                self.current_process = subprocess.Popen(
                    cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )

                self.current_source = "camera"
                logger.info(f"Kamera yayını başlatıldı: {camera_url}")
                return True, "Kamera yayını başlatıldı"

            except Exception as e:
                logger.error(f"Kamera yayını hatası: {e}")
                return False, f"Hata: {str(e)}"

    def play_slideshow(self, images=None, interval=5):
        """Resim slayt gösterisi oynat"""
        if not images:
            image_files = self.get_image_files()
            if not image_files:
                logger.error("Slayt için resim bulunamadı")
                return False, "Resim bulunamadı"
            image_paths = [os.path.join(IMAGE_DIR, f) for f in image_files]
        else:
            image_paths = [os.path.join(IMAGE_DIR, img) for img in images]

        self.stop_current()
        self.pause_automation()

        with self.lock:
            try:
                cmd = (
                    ["mpv"]
                    + self.config.get("mpv_options", [])
                    + [f"--image-display-duration={interval}", "--loop-playlist=inf"]
                    + image_paths
                )
                self.current_process = subprocess.Popen(cmd)
                self.current_source = "slayt"
                logger.info(
                    f"Slayt gösterisi başlatıldı. Gösterilecek resim sayısı: {len(image_paths)}"
                )
                return True, "Slayt gösterisi başlatıldı"
            except Exception as e:
                logger.error(f"Slayt gösterisi hatası: {e}")
                return False, f"Hata: {str(e)}"

    def get_status(self):
        """Mevcut durumu getir"""
        with self.lock:
            if self.current_process and self.current_process.poll() is None:
                return {
                    "playing": True,
                    "source": self.current_source,
                    "status": f"{self.current_source.capitalize()} oynatılıyor",
                    "automation_paused": self.automation_paused,
                }
            else:
                return {
                    "playing": False,
                    "source": None,
                    "status": "Beklemede",
                    "automation_paused": self.automation_paused,
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
        cams = self.config.setdefault("cameras", [])
        cams.append({"name": name, "url": url})
        self.save_config()

    def add_camera_with_details(self, camera_data):
        """Detaylı kamera bilgileriyle kamera ekle"""
        cams = self.config.setdefault("cameras", [])
        cams.append(camera_data)
        self.save_config()

    def remove_camera(self, name):
        cams = self.config.get("cameras", [])
        self.config["cameras"] = [c for c in cams if c.get("name") != name]
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


@app.route("/")
def index():
    """Ana sayfa"""
    return render_template("dashboard.html")


@app.route("/dashboard")
def dashboard():
    """Gelişmiş kontrol paneli"""
    return render_template("dashboard.html")


@app.route("/status")
def status():
    """Sistem durumu"""
    return jsonify(player.get_status())


@app.route("/videos")
def videos():
    return jsonify({"videos": player.get_video_files()})


@app.route("/images")
def images():
    return jsonify({"images": player.get_image_files()})


@app.route("/play_video", methods=["POST"])
def play_video():
    """Video oynatma endpoint'i"""
    logger.info("Video oynatma isteği alındı")
    data = request.get_json(silent=True) or {}
    videos = data.get("videos")
    success, message = player.play_video(videos)

    return jsonify(
        {"success": success, "message": message, "status": player.get_status()}
    )


@app.route("/play_camera", methods=["POST"])
def play_camera():
    """Kamera yayını endpoint'i"""
    logger.info("Kamera yayını isteği alındı")
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    success, message = player.play_camera(name)

    return jsonify(
        {"success": success, "message": message, "status": player.get_status()}
    )


@app.route("/play_slideshow", methods=["POST"])
def play_slideshow():
    """Slayt gösterisi endpoint'i"""
    logger.info("Slayt gösterisi isteği alındı")
    data = request.get_json(silent=True) or {}
    images = data.get("images")
    interval = data.get("interval", 5)
    success, message = player.play_slideshow(images, interval)
    return jsonify(
        {"success": success, "message": message, "status": player.get_status()}
    )


@app.route("/stop", methods=["POST"])
def stop():
    """Oynatmayı durdur"""
    logger.info("Durdurma isteği alındı")
    success = player.stop_current()

    return jsonify(
        {
            "success": success,
            "message": "Oynatma durduruldu" if success else "Hata oluştu",
            "status": player.get_status(),
        }
    )


@app.route("/announce", methods=["POST"])
def announce():
    data = request.get_json(force=True)
    message = data.get("message", "") if data else ""
    logger.info("Duyuru istegi alindi")
    success, msg = player.show_announcement(message)
    return jsonify({"success": success, "message": msg})


@app.route("/upload", methods=["POST"])
def upload():
    if "files[]" not in request.files:
        return jsonify({"success": False, "message": "Dosya bulunamadı"})

    files = request.files.getlist("files[]")

    for file in files:
        if file:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

    return jsonify({"success": True, "message": "Dosyalar yüklendi"})


@app.route("/upload_image", methods=["POST"])
def upload_image():
    if "files[]" not in request.files:
        return jsonify({"success": False, "message": "Dosya bulunamadı"})

    files = request.files.getlist("files[]")

    for file in files:
        if file:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["IMAGE_UPLOAD_FOLDER"], filename))

    return jsonify({"success": True, "message": "Görseller yüklendi"})


@app.route("/delete_video", methods=["POST"])
def delete_video():
    """Video sil"""
    data = request.get_json(silent=True) or {}
    filename = data.get("filename")
    if not filename:
        return jsonify({"success": False, "message": "Dosya adı belirtilmedi"})

    try:
        filepath = os.path.join(VIDEO_DIR, secure_filename(filename))
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f"Video silindi: {filename}")
            return jsonify({"success": True, "message": "Video başarıyla silindi"})
        else:
            return jsonify({"success": False, "message": "Dosya bulunamadı"})
    except Exception as e:
        logger.error(f"Video silinirken hata: {e}")
        return jsonify({"success": False, "message": str(e)})


@app.route("/delete_image", methods=["POST"])
def delete_image():
    """Görsel sil"""
    data = request.get_json(silent=True) or {}
    filename = data.get("filename")
    if not filename:
        return jsonify({"success": False, "message": "Dosya adı belirtilmedi"})

    try:
        filepath = os.path.join(IMAGE_DIR, secure_filename(filename))
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f"Görsel silindi: {filename}")
            return jsonify({"success": True, "message": "Görsel başarıyla silindi"})
        else:
            return jsonify({"success": False, "message": "Dosya bulunamadı"})
    except Exception as e:
        logger.error(f"Görsel silinirken hata: {e}")
        return jsonify({"success": False, "message": str(e)})


@app.route("/cameras", methods=["GET", "POST", "DELETE"])
def cameras():
    if request.method == "GET":
        return jsonify({"cameras": player.config.get("cameras", [])})
    data = request.get_json(force=True)
    name = data.get("name")
    if request.method == "POST":
        url = data.get("url")
        username = data.get("username")
        password = data.get("password")
        ip = data.get("ip")
        port = data.get("port")
        discovered = data.get("discovered", False)

        # Keşfedilen kameralar için ek bilgileri kaydet
        camera_data = {"name": name, "url": url}

        if discovered and username and password:
            camera_data.update(
                {
                    "username": username,
                    "password": password,
                    "ip": ip,
                    "port": port,
                    "discovered": True,
                }
            )

        player.add_camera_with_details(camera_data)
    elif request.method == "DELETE":
        player.remove_camera(name)
    return jsonify({"success": True})


@app.route("/resume", methods=["POST"])
def resume():
    player.resume_automation()
    return jsonify({"success": True})


@app.route("/system_info")
def system_info():
    temp = "N/A"
    disk = "N/A"
    try:
        out = subprocess.check_output(["vcgencmd", "measure_temp"]).decode()
        temp = out.strip().split("=")[1]
    except Exception:
        logger.warning("İşlemci sıcaklığı okunamadı (vcgencmd komutu bulunamadı?).")

    try:
        out = (
            subprocess.check_output(["df", "-h", "/"]).decode().splitlines()[1].split()
        )
        disk = f"{out[2]} / {out[1]} ({out[4]})"
    except Exception:
        logger.warning("Disk bilgisi okunamadı.")

    try:
        mem = psutil.virtual_memory()
        mem_percent = mem.percent
        mem_total = f"{mem.total / (1024**3):.2f} GB"
        mem_used = f"{mem.used / (1024**3):.2f} GB"
    except Exception as e:
        logger.warning(f"Hafıza bilgisi okunamadı: {e}")
        mem_percent, mem_total, mem_used = "N/A", "N/A", "N/A"

    try:
        cpu = psutil.cpu_percent(interval=1)
    except Exception as e:
        logger.warning(f"İşlemci kullanımı okunamadı: {e}")
        cpu = "N/A"

    try:
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = str(datetime.now() - boot_time).split(".")[0]
    except Exception as e:
        logger.warning(f"Çalışma süresi okunamadı: {e}")
        uptime = "N/A"

    return jsonify(
        {
            "temperature": temp,
            "disk_usage": disk,
            "cpu_usage": cpu,
            "memory": {"percent": mem_percent, "total": mem_total, "used": mem_used},
            "uptime": uptime,
        }
    )


@app.route("/logs")
def logs():
    """Logları getir"""
    try:
        log_files = sorted(
            [os.path.join(LOG_DIR, f) for f in os.listdir(LOG_DIR)],
            key=os.path.getmtime,
            reverse=True,
        )
        if not log_files:
            return jsonify({"success": False, "logs": "Log dosyası bulunamadı"})

        with open(log_files[0], "r", encoding="utf-8") as f:
            # Son 100 satırı oku
            lines = f.readlines()
            last_100_lines = lines[-100:]

        return jsonify({"success": True, "logs": "".join(last_100_lines)})
    except Exception as e:
        logger.error(f"Loglar okunurken hata: {e}")
        return jsonify({"success": False, "logs": str(e)})


def discover_onvif_cameras():
    """Ağdaki tüm arayüzleri tarayarak ONVIF kameralarını keşfet"""
    discovered_cameras = []

    try:
        from onvif import ONVIFCamera
        import netifaces

        logger.info("ONVIF kamera keşfi başlatıldı.")

        def check_onvif_camera(ip):
            """Belirli bir IP'de ONVIF kamerası olup olmadığını kontrol et"""
            try:
                # Standart ONVIF portu 80'dir, ancak bazı kameralar farklı portlar kullanabilir.
                # Şimdilik sadece port 80'i kontrol ediyoruz.
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                if sock.connect_ex((ip, 80)) == 0:
                    sock.close()
                    logger.info(f"IP {ip}: Port 80 açık, ONVIF kontrol ediliyor...")
                    cam = ONVIFCamera(ip, 80, "", "")
                    hostname = cam.devicemgmt.GetHostname().Name
                    logger.info(f"ONVIF kamera bulundu: IP={ip}, Hostname={hostname}")
                    return {"ip": ip, "port": 80, "hostname": hostname}
                sock.close()
            except Exception as e:
                # Hata loglaması keşif sürecini yavaşlatabilir, bu yüzden sadece debug seviyesinde logla
                # logger.debug(f"IP {ip} kontrol edilirken hata: {e}")
                pass
            return None

        subnets = set()
        for iface in netifaces.interfaces():
            ifaddrs = netifaces.ifaddresses(iface)
            if netifaces.AF_INET in ifaddrs:
                for addr_info in ifaddrs[netifaces.AF_INET]:
                    ip = addr_info.get("addr")
                    netmask = addr_info.get("netmask")
                    if ip and netmask and not ip.startswith("127."):
                        try:
                            # Subnet'i hesapla (örn: 192.168.1.0)
                            ip_parts = list(map(int, ip.split(".")))
                            mask_parts = list(map(int, netmask.split(".")))
                            net_start = [ip_parts[i] & mask_parts[i] for i in range(4)]
                            subnet = ".".join(map(str, net_start[:3]))
                            subnets.add(subnet)
                        except ValueError:
                            logger.warning(
                                f"Geçersiz IP/Netmask formatı: {ip}/{netmask}"
                            )

        if not subnets:
            logger.warning("Taranacak ağ arayüzü bulunamadı.")
            return []

        logger.info(f"Taranacak ağlar: {list(subnets)}")

        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = []
            for subnet_base in subnets:
                for i in range(1, 255):
                    ip_to_check = f"{subnet_base}.{i}"
                    futures.append(executor.submit(check_onvif_camera, ip_to_check))

            for future in as_completed(futures):
                result = future.result()
                if result:
                    discovered_cameras.append(result)

        logger.info(
            f"Keşif tamamlandı. Toplam {len(discovered_cameras)} kamera bulundu."
        )
        return discovered_cameras

    except ImportError:
        logger.error(
            "Gerekli kütüphaneler (onvif-py3, netifaces) yüklü değil. Keşif yapılamıyor."
        )
        return []
    except Exception as e:
        logger.error(
            f"Kamera keşfi sırasında beklenmedik bir hata oluştu: {e}", exc_info=True
        )
        return []


@app.route("/discover_cameras", methods=["POST"])
def discover_cameras():
    """Ağdaki kameraları keşfet"""
    logger.info("Kamera keşfi isteği alındı")
    try:
        cameras = discover_onvif_cameras()
        return jsonify({"success": True, "cameras": cameras})
    except Exception as e:
        logger.error(f"Kamera keşfi API hatası: {e}")
        return jsonify({"success": False, "message": str(e)})


def startup_sequence():
    """Başlangıç dizisi - fallback mantığı"""
    delay = player.config.get("startup_delay", 5)
    logger.info(f"{delay} saniye bekleniyor...")
    time.sleep(delay)

    try:
        # Varsayılan videoyu oynat
        success, message = player.play_video()
        if not success:
            logger.error(f"Başlangıç videosu oynatılamadı: {message}")
    except Exception as e:
        logger.error(f"Başlangıç dizisi hatası: {e}")


def signal_handler(sig, frame):
    """Graceful shutdown"""
    logger.info("Kapatma sinyali alındı")
    try:
        player.stop_current()
        player.scheduler.shutdown()
    except Exception as e:
        logger.error(f"Kapatma sırasında hata: {e}")
    os._exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Başlangıç dizisini ayrı bir thread'de çalıştır
    startup_thread = threading.Thread(target=startup_sequence)
    startup_thread.daemon = True
    startup_thread.start()

    logger.info("Web sunucusu başlatılıyor...")
    app.run(host="0.0.0.0", port=player.config.get("web_port", 5000), debug=False)
