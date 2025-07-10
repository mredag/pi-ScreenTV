// Pi-Ekran JavaScript Kontrol Kodu

class PiEkranController {
    constructor() {
        this.isProcessing = false;
        this.statusCheckInterval = null;
        
        // DOM elementleri
        this.elements = {
            statusIndicator: document.getElementById('statusIndicator'),
            statusText: document.getElementById('statusText'),
            playVideoBtn: document.getElementById('playVideoBtn'),
            playCameraBtn: document.getElementById('playCameraBtn'),
            stopBtn: document.getElementById('stopBtn'),
            announceBtn: document.getElementById("announceBtn"),
            uploadInput: document.getElementById('uploadInput'),
            uploadBtn: document.getElementById('uploadBtn'),
            resumeBtn: document.getElementById('resumeBtn'),
            cameraList: document.getElementById('cameraList'),
            videoList: document.getElementById('videoList'),
            currentSource: document.getElementById('currentSource'),
            systemStatus: document.getElementById('systemStatus'),
            lastUpdate: document.getElementById('lastUpdate'),
            cpuTemp: document.getElementById('cpuTemp'),
            diskUsage: document.getElementById('diskUsage'),
            logContainer: document.getElementById('logContainer')
        };
        
        // Event listener'ları ekle
        this.bindEvents();
        
        // Durumu kontrol et
        this.checkStatus();
        
        // Periyodik durum kontrolü başlat
        this.startStatusChecking();

        // Videoları yükle
        this.loadVideos();
    }
    
    bindEvents() {
        this.elements.playVideoBtn.addEventListener('click', () => this.playVideo());
        this.elements.playCameraBtn.addEventListener('click', () => this.playCamera());
        this.elements.stopBtn.addEventListener('click', () => this.stop());
        this.elements.announceBtn.addEventListener('click', () => this.announce());
        this.elements.uploadBtn.addEventListener('click', () => this.upload());
        this.elements.resumeBtn.addEventListener('click', () => this.resume());
    }
    
    startStatusChecking() {
        // Her 5 saniyede bir durumu kontrol et
        this.statusCheckInterval = setInterval(() => {
            if (!this.isProcessing) {
                this.checkStatus();
            }
        }, 5000);
    }
    
    async checkStatus() {
        try {
            const [statusRes, infoRes, camRes] = await Promise.all([
                fetch('/status'),
                fetch('/system_info'),
                fetch('/cameras')
            ]);
            const status = await statusRes.json();
            const info = await infoRes.json();
            const cams = await camRes.json();
            this.updateUI(status, info, cams);
        } catch (error) {
            this.handleError('Sunucuya bağlanılamıyor');
        }
    }
    
    updateUI(status, info, cams) {
        // Durum göstergesini güncelle
        this.elements.statusIndicator.className = 'status-indicator';
        
        if (status.playing) {
            this.elements.statusIndicator.classList.add('playing');
            this.elements.statusText.textContent = status.status;
        } else {
            this.elements.statusIndicator.classList.add('connected');
            this.elements.statusText.textContent = 'Bağlı - Beklemede';
        }
        
        // Bilgileri güncelle
        this.elements.currentSource.textContent = status.source ? 
            (status.source === 'video' ? 'Tanıtım Videosu' : 'Canlı Kamera') : 
            'Yok';
        this.elements.systemStatus.textContent = status.playing ? 'Oynatılıyor' : 'Beklemede';
        this.elements.lastUpdate.textContent = new Date().toLocaleTimeString('tr-TR');
        
        // Butonları güncelle
        this.updateButtons(status);
        if (info) {
            this.elements.cpuTemp.textContent = info.temperature;
            this.elements.diskUsage.textContent = info.disk_usage;
        }
        if (cams && cams.cameras) {
            this.renderCameraList(cams.cameras);
        }
    }
    
    updateButtons(status) {
        if (!this.isProcessing) {
            this.elements.playVideoBtn.disabled = false;
            this.elements.playCameraBtn.disabled = false;
            this.elements.announceBtn.disabled = false;
            this.elements.stopBtn.disabled = !status.playing;
            this.elements.uploadBtn.disabled = false;
            this.elements.resumeBtn.disabled = !status.automation_paused;
            
            // Buton durumlarını güncelle
            this.elements.playVideoBtn.classList.remove('loading');
            this.elements.playCameraBtn.classList.remove('loading');
            this.elements.stopBtn.classList.remove('loading');
            this.elements.announceBtn.classList.remove('loading');
        }
    }
    
    async playVideo() {
        if (this.isProcessing) return;

        const selected = Array.from(document.querySelectorAll('#videoList input[type="checkbox"]:checked')).map(c => c.value);

        this.isProcessing = true;
        this.disableAllButtons();
        this.elements.playVideoBtn.classList.add('loading');
        this.addLog('Video oynatma isteği gönderiliyor...');

        try {
            const response = await fetch('/play_video', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({videos: selected})
            });
            const data = await response.json();
            
            if (data.success) {
                this.addLog('Video oynatma başarıyla başlatıldı', 'success');
                this.updateUI(data.status);
            } else {
                this.addLog(`Hata: ${data.message}`, 'error');
            }
        } catch (error) {
            this.handleError('Video oynatma hatası');
        } finally {
            this.isProcessing = false;
            this.elements.playVideoBtn.classList.remove('loading');
        }
    }
    
    async playCamera() {
        if (this.isProcessing) return;
        
        this.isProcessing = true;
        this.disableAllButtons();
        this.elements.playCameraBtn.classList.add('loading');
        this.addLog('Kamera yayını isteği gönderiliyor...');
        
        try {
            const response = await fetch('/play_camera', { method: 'POST' });
            const data = await response.json();
            
            if (data.success) {
                this.addLog('Kamera yayını başarıyla başlatıldı', 'success');
                this.updateUI(data.status);
            } else {
                this.addLog(`Hata: ${data.message}`, 'error');
            }
        } catch (error) {
            this.handleError('Kamera yayını hatası');
        } finally {
            this.isProcessing = false;
            this.elements.playCameraBtn.classList.remove('loading');
        }
    }

    async playCameraByName(name) {
        if (this.isProcessing) return;
        this.isProcessing = true;
        this.disableAllButtons();
        this.addLog('Kamera yayını isteği gönderiliyor...');
        try {
            const response = await fetch('/play_camera', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({name})
            });
            const data = await response.json();
            if (data.success) {
                this.addLog('Kamera yayını başarıyla başlatıldı', 'success');
                this.updateUI(data.status);
            } else {
                this.addLog(`Hata: ${data.message}`, 'error');
            }
        } catch (e) {
            this.handleError('Kamera yayını hatası');
        } finally {
            this.isProcessing = false;
        }
    }
    
    async stop() {
        if (this.isProcessing) return;
        
        this.isProcessing = true;
        this.disableAllButtons();
        this.elements.stopBtn.classList.add('loading');
        this.addLog('Durdurma isteği gönderiliyor...');
        
        try {
            const response = await fetch('/stop', { method: 'POST' });
            const data = await response.json();
            
            if (data.success) {
                this.addLog('Oynatma başarıyla durduruldu', 'success');
                this.updateUI(data.status);
            } else {
                this.addLog(`Hata: ${data.message}`, 'error');
            }
        } catch (error) {
            this.handleError('Durdurma hatası');

        } finally {
            this.isProcessing = false;
            this.elements.stopBtn.classList.remove('loading');
        }
    }

    async loadVideos() {
        try {
            const response = await fetch('/videos');
            const data = await response.json();
            this.renderVideoList(data.videos || []);
        } catch (e) {
            this.addLog('Video listesi alınamadı', 'error');
        }
    }

    renderVideoList(list) {
        this.elements.videoList.innerHTML = '';
        list.forEach(name => {
            const label = document.createElement('label');
            label.className = 'video-item';
            const cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.value = name;
            label.appendChild(cb);
            label.appendChild(document.createTextNode(' ' + name));
            this.elements.videoList.appendChild(label);
        });
    }

    renderCameraList(list) {
        this.elements.cameraList.innerHTML = '';
        list.forEach(cam => {
            const btn = document.createElement('button');
            btn.textContent = cam.name;
            btn.className = 'camera-item';
            btn.addEventListener('click', () => this.playCameraByName(cam.name));
            this.elements.cameraList.appendChild(btn);
        });
    }

    async upload() {
        const file = this.elements.uploadInput.files[0];
        if (!file) return;
        const form = new FormData();
        form.append('file', file);
        this.isProcessing = true;
        this.disableAllButtons();
        try {
            const res = await fetch('/upload', {method: 'POST', body: form});
            const data = await res.json();
            if (data.success) {
                this.addLog('Video yüklendi', 'success');
                this.loadVideos();
            } else {
                this.addLog('Yükleme hatası', 'error');
            }
        } catch (e) {
            this.addLog('Yükleme hatası', 'error');
        } finally {
            this.isProcessing = false;
            this.updateButtons({playing:false});
        }
    }

    async resume() {
        this.isProcessing = true;
        this.disableAllButtons();
        try {
            await fetch('/resume', {method: 'POST'});
            this.addLog('Otomasyon devam ediyor', 'success');
            this.checkStatus();
        } finally {
            this.isProcessing = false;
            this.updateButtons({playing:false});
        }
    }

    async announce() {
        const text = prompt("Duyuru metni:");
        if (!text) return;
        this.isProcessing = true;
        this.disableAllButtons();
        this.elements.announceBtn.classList.add("loading");
        this.addLog("Duyuru gönderiliyor...");
        try {
            const response = await fetch("/announce", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({ message: text })
            });
            const data = await response.json();
            if (data.success) {
                this.addLog("Duyuru gösterildi", "success");
            } else {
                this.addLog(`Hata: ${data.message}`, "error");
            }
        } catch (error) {
            this.handleError("Duyuru hatası");
        } finally {
            this.isProcessing = false;
            this.elements.announceBtn.classList.remove("loading");
        }
    }
    disableAllButtons() {
        this.elements.playVideoBtn.disabled = true;
        this.elements.playCameraBtn.disabled = true;
        this.elements.stopBtn.disabled = true;
        this.elements.announceBtn.disabled = true;
        this.elements.uploadBtn.disabled = true;
        this.elements.resumeBtn.disabled = true;
    }
    
    handleError(message) {
        this.elements.statusIndicator.className = 'status-indicator error';
        this.elements.statusText.textContent = 'Bağlantı Hatası';
        this.addLog(message, 'error');
        
        // Butonları devre dışı bırak
        this.disableAllButtons();
    }
    
    addLog(message, type = 'normal') {
        const timestamp = new Date().toLocaleTimeString('tr-TR');
        const entry = document.createElement('p');
        entry.className = 'log-entry';
        
        if (type === 'error') {
            entry.classList.add('error');
        } else if (type === 'success') {
            entry.classList.add('success');
        }
        
        entry.textContent = `[${timestamp}] ${message}`;
        
        // Log konteynerının başına ekle
        this.elements.logContainer.insertBefore(entry, this.elements.logContainer.firstChild);
        
        // Maksimum 50 log tut
        while (this.elements.logContainer.children.length > 50) {
            this.elements.logContainer.removeChild(this.elements.logContainer.lastChild);
        }
    }
}

// Sayfa yüklendiğinde kontrolcüyü başlat
document.addEventListener('DOMContentLoaded', () => {
    window.piEkran = new PiEkranController();
});

