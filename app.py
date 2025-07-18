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
from flask import (
    Flask,
    render_template,
    jsonify,
    request,
    redirect,
    url_for,
    flash,
    Response,
    stream_with_context,
)
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
)

from werkzeug.security import check_password_hash, generate_password_hash
from threading import Lock
from apscheduler.schedulers.background import BackgroundScheduler
import signal
import socket
import threading
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from werkzeug.utils import secure_filename
import psutil
import shutil

# Uygulama dizini
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
LOG_DIR = os.path.join(BASE_DIR, "logs")
VIDEO_DIR = os.path.join(BASE_DIR, "videos")
IMAGE_DIR = os.path.join(BASE_DIR, "static", "images")
MPV_LOG_FILE = os.path.join(LOG_DIR, "mpv.log")


def load_app_config():
    """Yapılandırma dosyasını oku ve varsayılan değerleri ata."""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        config = {}

    config.setdefault("SECRET_KEY", "change-me")
    config.setdefault("USERNAME", "admin")
    config.setdefault("PASSWORD_HASH", "")
    config.setdefault("log_level", "INFO")
    config.setdefault("enable_mpv_logging", False)
    config.setdefault("startup_delay", 5)
    config.setdefault("web_port", 5000)
    config.setdefault(
        "mpv_options",
        ["--fullscreen", "--no-osc", "--no-input-default-bindings"],
    )
    config.setdefault("cameras", [])

    return config


app_config = load_app_config()


def get_mpv_log_tail(lines: int = 10) -> str:
    """Return the last few lines of the MPV log file for diagnostics."""
    try:
        with open(MPV_LOG_FILE, "r", encoding="utf-8") as f:
            return "".join(f.readlines()[-lines:])
    except Exception as e:
        logger.error(f"MPV log okunamadi: {e}")
        return ""

# Log dizinini oluştur
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)
os.makedirs(IMAGE_DIR, exist_ok=True)

# Logging yapılandırması
log_level = app_config.get("log_level", "INFO").upper()
level_value = getattr(logging, log_level, logging.INFO)
logging.basicConfig(
    level=level_value,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(
            os.path.join(LOG_DIR, f"pi-ekran_{datetime.now().strftime('%Y%m%d')}.log"),
            encoding="utf-8",
        ),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("PiEkran")

# Flask uygulaması
app = Flask(__name__)
app.config.from_mapping(app_config)
app.config["UPLOAD_FOLDER"] = VIDEO_DIR
app.config["IMAGE_UPLOAD_FOLDER"] = IMAGE_DIR
# Remove upload size limit
# Flask checks MAX_CONTENT_LENGTH and rejects requests larger than this
# value with a 413 status. Some versions of Flask assume this key exists,
# so set it explicitly to ``None`` to disable the limit.
app.config["MAX_CONTENT_LENGTH"] = None

# Flask-Login kurulumu
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)


class User(UserMixin):
    def __init__(self, username: str):
        self.id = username


@login_manager.user_loader
def load_user(user_id):
    if user_id == app.config.get("USERNAME"):
        return User(user_id)
    return None



@login_manager.unauthorized_handler
def unauthorized_callback():
    if request.is_json:
        return jsonify({"success": False, "message": "Oturum gerekli"}), 401
    return redirect(url_for("login"))



class MediaPlayer:
    """MPV media player kontrolcüsü"""

    def __init__(self):
        self.current_process = None
        self.current_source = None
        self.lock = Lock()
        self.automation_paused = False
        self.config = self.load_config()

        log_level = self.config.get("log_level", "INFO").upper()
        level_value = getattr(logging, log_level, logging.INFO)
        logger.setLevel(level_value)
        logging.getLogger().setLevel(level_value)

        self.videos = self.get_video_files()

        self.scheduler = BackgroundScheduler(timezone="Europe/Istanbul")
        self.start_scheduler()

        if not os.environ.get("DISPLAY"):
            logger.warning("DISPLAY değişkeni tanımsız. mpv görüntü açamayabilir.")

    def load_config(self):
        """Yapılandırma dosyasını yükle"""
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                logger.info("Yapılandırma dosyası yüklendi")
                config.setdefault("enable_mpv_logging", False)
                config.setdefault("log_level", "INFO")
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
                "SECRET_KEY": "change-me",
                "USERNAME": "admin",
                "PASSWORD_HASH": "",
                "enable_mpv_logging": False,
                "log_level": "INFO",
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
        if not shutil.which("mpv"):
            logger.error("mpv oynaticisi bulunamadi")
            return False, "mpv yüklü değil"
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
                cmd = ["mpv"] + self.config.get("mpv_options", [])
                cmd += ["--input-ipc-server=/tmp/mpvsocket", "--loop-playlist=inf"]
                cmd += video_paths
                if self.config.get("enable_mpv_logging", False):
                    cmd.append(f"--log-file={MPV_LOG_FILE}")

                if self.config.get("enable_mpv_logging", False):
                    log_target = open(MPV_LOG_FILE, "a")
                else:
                    open(MPV_LOG_FILE, "a").close()
                    log_target = subprocess.DEVNULL
                try:
                    self.current_process = subprocess.Popen(cmd, stdout=log_target, stderr=log_target)
                finally:
                    if log_target is not subprocess.DEVNULL:
                        log_target.close()

                time.sleep(1)
                if self.current_process.poll() is not None:
                    logger.error(
                        f"mpv başlatılamadı. Çıkış kodu: {self.current_process.returncode}"
                    )
                    tail = get_mpv_log_tail()
                    msg = "mpv başlatılamadı"
                    if tail:
                        msg += f"\n{tail}"
                    return False, msg

                self.current_source = "video"
                logger.info(f"Video oynatılıyor: {video_paths}")
                return True, "Video oynatma başlatıldı"

            except Exception as e:
                logger.error(f"Video oynatma hatası: {e}")
                return False, f"Hata: {str(e)}"

    def play_camera(self, name=None):
        """Kamera yayınını göster"""
        if not shutil.which("mpv"):
            logger.error("mpv oynaticisi bulunamadi")
            return False, "mpv yüklü değil"
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
                cmd = ["mpv"] + self.config.get("mpv_options", [])
                cmd += ["--input-ipc-server=/tmp/mpvsocket", camera_url]
                if self.config.get("enable_mpv_logging", False):
                    cmd.append(f"--log-file={MPV_LOG_FILE}")

                if self.config.get("enable_mpv_logging", False):
                    log_target = open(MPV_LOG_FILE, "a")
                else:
                    open(MPV_LOG_FILE, "a").close()
                    log_target = subprocess.DEVNULL
                try:
                    self.current_process = subprocess.Popen(cmd, stdout=log_target, stderr=log_target)
                finally:
                    if log_target is not subprocess.DEVNULL:
                        log_target.close()

                time.sleep(1)
                if self.current_process.poll() is not None:
                    logger.error(
                        f"mpv başlatılamadı. Çıkış kodu: {self.current_process.returncode}"
                    )
                    tail = get_mpv_log_tail()
                    msg = "mpv başlatılamadı"
                    if tail:
                        msg += f"\n{tail}"
                    return False, msg

                self.current_source = "camera"
                logger.info(f"Kamera yayını başlatıldı: {camera_url}")
                return True, "Kamera yayını başlatıldı"

            except Exception as e:
                logger.error(f"Kamera yayını hatası: {e}")
                return False, f"Hata: {str(e)}"

    def play_slideshow(self, images=None, interval=5):
        """Resim slayt gösterisi oynat"""
        if not shutil.which("mpv"):
            logger.error("mpv oynaticisi bulunamadi")
            return False, "mpv yüklü değil"
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
                cmd = ["mpv"] + self.config.get("mpv_options", [])
                cmd += [f"--image-display-duration={interval}", "--loop-playlist=inf"]
                if self.config.get("enable_mpv_logging", False):
                    cmd.append(f"--log-file={MPV_LOG_FILE}")
                cmd += image_paths

                if self.config.get("enable_mpv_logging", False):
                    log_target = open(MPV_LOG_FILE, "a")
                else:
                    open(MPV_LOG_FILE, "a").close()
                    log_target = subprocess.DEVNULL
                try:
                    self.current_process = subprocess.Popen(cmd, stdout=log_target, stderr=log_target)
                finally:
                    if log_target is not subprocess.DEVNULL:
                        log_target.close()

                time.sleep(1)
                if self.current_process.poll() is not None:
                    logger.error(
                        f"mpv başlatılamadı. Çıkış kodu: {self.current_process.returncode}"
                    )
                    tail = get_mpv_log_tail()
                    msg = "mpv başlatılamadı"
                    if tail:
                        msg += f"\n{tail}"
                    return False, msg
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

# Konfigürasyondan gizli anahtar ve kullanıcı bilgilerini al
app.config["SECRET_KEY"] = player.config.get("SECRET_KEY", "change-me")
app.config["USERNAME"] = player.config.get("USERNAME", "admin")
app.config["PASSWORD_HASH"] = player.config.get("PASSWORD_HASH", "")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        remember = bool(request.form.get("remember"))

        if (
            username == app.config.get("USERNAME")
            and check_password_hash(app.config.get("PASSWORD_HASH", ""), password)
        ):
            login_user(User(username), remember=remember)
            flash("Başarıyla giriş yapıldı", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Kullanıcı adı veya şifre hatalı", "error")

    return render_template("login.html", now=datetime.now())


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Çıkış yapıldı", "success")
    return redirect(url_for("login"))



@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current = request.form.get("current_password")
        new_pass = request.form.get("new_password")
        confirm = request.form.get("confirm_password")

        if not check_password_hash(app.config.get("PASSWORD_HASH", ""), current):
            flash("Mevcut şifre hatalı", "error")
        elif new_pass != confirm:
            flash("Yeni şifreler eşleşmiyor", "error")
        else:
            new_hash = generate_password_hash(new_pass)
            app.config["PASSWORD_HASH"] = new_hash
            player.config["PASSWORD_HASH"] = new_hash
            player.save_config()
            flash("Şifre güncellendi", "success")
            return redirect(url_for("dashboard"))

    return render_template("change_password.html")


@app.route("/")
@login_required
def index():
    """Ana sayfa"""
    return render_template("dashboard.html")


@app.route("/dashboard")
@login_required
def dashboard():
    """Gelişmiş kontrol paneli"""
    return render_template("dashboard.html")


@app.route("/status")
@login_required
def status():
    """Sistem durumu"""
    return jsonify(player.get_status())


@app.route("/videos")
@login_required
def videos():
    return jsonify({"videos": player.get_video_files()})


@app.route("/images")
@login_required
def images():
    return jsonify({"images": player.get_image_files()})


@app.route("/play_video", methods=["POST"])
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
def announce():
    data = request.get_json(force=True)
    message = data.get("message", "") if data else ""
    logger.info("Duyuru istegi alindi")
    success, msg = player.show_announcement(message)
    return jsonify({"success": success, "message": msg})


@app.route("/upload", methods=["POST"])
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
def resume():
    player.resume_automation()
    return jsonify({"success": True})


@app.route("/system_info")
@login_required
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
@login_required
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


def discover_onvif_cameras(progress_callback=None):
    """Ağdaki tüm arayüzleri tarayarak ONVIF kameralarını keşfet (geliştirilmiş sürüm)"""
    discovered_cameras = []

    # Yaygın ONVIF portları. Bazı kameralar yönetim için farklı portlar kullanabilir.
    COMMON_ONVIF_PORTS = [80, 8080, 8000, 2020]

    try:
        from onvif import ONVIFCamera
        import netifaces
        import zeep

        logger.info("Geliştirilmiş ONVIF kamera keşfi başlatıldı.")

        def check_onvif_camera(ip, port):
            """Belirli bir IP ve portta ONVIF kamerası olup olmadığını kontrol et"""
            if progress_callback:
                progress_callback({"event": "scan", "ip": ip, "port": port})
            try:
                # Öncelikle portun açık olup olmadığını hızlıca kontrol et
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(0.5)
                    if sock.connect_ex((ip, port)) != 0:
                        return None

                cam = ONVIFCamera(ip, port, "", "", no_cache=True)

                # Hostname bilgisi
                try:
                    hostname = cam.devicemgmt.GetHostname().Name
                except Exception:
                    logger.warning(f"IP {ip}:{port} için hostname alınamadı.")
                    hostname = f"ONVIF Camera ({ip})"

                # RTSP URI bilgisi
                rtsp_url = ""
                try:
                    media_profiles = cam.media.GetProfiles()
                    if media_profiles:
                        token = media_profiles[0].token
                        req = cam.media.create_type("GetStreamUri")
                        req.ProfileToken = token
                        req.StreamSetup = {"Stream": "RTP-Unicast", "Transport": {"Protocol": "RTSP"}}
                        rtsp_url = cam.media.GetStreamUri(req).Uri
                except zeep.exceptions.Fault as e:
                    logger.warning(
                        f"IP {ip}:{port} için stream URI alınamadı (Yetkilendirme gerekebilir): {e}"
                    )
                except Exception:
                    logger.warning(f"IP {ip}:{port} için stream URI alınamadı (Genel Hata).")

                result = {"ip": ip, "port": port, "hostname": hostname, "rtsp_url": rtsp_url}
                logger.info(
                    f"ONVIF kamera bulundu: IP={ip}:{port}, Hostname={hostname}, RTSP={rtsp_url or 'Bulunamadı'}"
                )

                if progress_callback:
                    progress_callback({"event": "found", "camera": result})

                return result
            except Exception:
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

        logger.info(f"Taranacak ağlar: {list(subnets)} üzerinde Portlar: {COMMON_ONVIF_PORTS}")

        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = []
            for subnet_base in subnets:
                for i in range(1, 255):
                    ip_to_check = f"{subnet_base}.{i}"
                    for port in COMMON_ONVIF_PORTS:
                        futures.append(executor.submit(check_onvif_camera, ip_to_check, port))

            for future in as_completed(futures):
                result = future.result()
                if result:
                    discovered_cameras.append(result)

        logger.info(
            f"Keşif tamamlandı. Toplam {len(discovered_cameras)} potansiyel kamera servisi bulundu."
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
@login_required
def discover_cameras():
    """Ağdaki kameraları keşfet"""
    logger.info("Kamera keşfi isteği alındı")
    try:
        cameras = discover_onvif_cameras()
        return jsonify({"success": True, "cameras": cameras})
    except Exception as e:
        logger.error(f"Kamera keşfi API hatası: {e}")
        return jsonify({"success": False, "message": str(e)})


@app.route("/discover_cameras_stream")
@login_required
def discover_cameras_stream():
    """Ağ taramasını SSE ile gerçekleştirmek için endpoint"""

    def event_stream():
        q = queue.Queue()

        def progress(data):
            q.put(data)

        def run_scan():
            cams = discover_onvif_cameras(progress_callback=progress)
            q.put({"event": "done", "cameras": cams})

        threading.Thread(target=run_scan, daemon=True).start()

        while True:
            item = q.get()
            event = item.get("event")
            if event == "done":
                yield f"event: done\ndata: {json.dumps(item['cameras'])}\n\n"
                break
            elif event == "found":
                yield f"event: found\ndata: {json.dumps(item['camera'])}\n\n"
            elif event == "scan":
                payload = json.dumps({"ip": item['ip'], "port": item['port']})
                yield f"event: scan\ndata: {payload}\n\n"

    return Response(stream_with_context(event_stream()), mimetype="text/event-stream")


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
