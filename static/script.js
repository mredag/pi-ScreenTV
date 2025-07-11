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
            stopBtn: document.getElementById('stopBtn'),
            announceBtn: document.getElementById("announceBtn"),
            uploadInput: document.getElementById('uploadInput'),
            imageUploadInput: document.getElementById('imageUploadInput'),
            resumeBtn: document.getElementById('resumeBtn'),
            cameraList: document.getElementById('cameraList'),
            videoList: document.getElementById('videoList'),
            currentSource: document.getElementById('currentSource'),
            playSlideshowBtn: document.getElementById('playSlideshowBtn'),
            lastUpdate: document.getElementById('lastUpdate'),
            cpuTemp: document.getElementById('cpuTemp'),
            diskUsage: document.getElementById('diskUsage'),
            logContainer: document.getElementById('logContainer'),
            cameraSettingsBtn: document.getElementById('cameraSettingsBtn'),
            cameraModal: document.getElementById('cameraModal'),
            closeModal: document.getElementById('closeModal'),
            modalCameraList: document.getElementById('modalCameraList'),
            addCameraForm: document.getElementById('addCameraForm'),
            cameraName: document.getElementById('cameraName'),
            cameraUrl: document.getElementById('cameraUrl'),
            scanNetworkBtn: document.getElementById('scanNetworkBtn'),
            scanButtonText: document.getElementById('scanButtonText'),
            scanResults: document.getElementById('scanResults'),
            discoveredCameras: document.getElementById('discoveredCameras'),
            credentialModal: document.getElementById('credentialModal'),
            closeCredentialModal: document.getElementById('closeCredentialModal'),
            credentialForm: document.getElementById('credentialForm'),
            discoveredCameraName: document.getElementById('discoveredCameraName'),
            cameraUsername: document.getElementById('cameraUsername'),
            cameraPassword: document.getElementById('cameraPassword'),
            slideshowModal: document.getElementById('slideshowModal'),
            closeSlideshowModal: document.getElementById('closeSlideshowModal'),
            slideshowForm: document.getElementById('slideshowForm'),
            slideshowImageList: document.getElementById('slideshowImageList'),
        };
        
        // Event listener'ları ekle
        this.bindEvents();
        
        // Durumu kontrol et
        this.checkStatus();
        this.checkSystemInfo();

        // Periyodik durum kontrolü başlat
        this.startStatusChecking();

        // Videoları yükle
        this.loadVideos();

        // Kameraları yükle
        this.loadCameras();
    }
    
    bindEvents() {
        this.elements.playVideoBtn.addEventListener('click', () => this.playVideo());
        this.elements.playSlideshowBtn.addEventListener('click', () => this.openSlideshowModal());
        this.elements.stopBtn.addEventListener('click', () => this.stop());
        this.elements.announceBtn.addEventListener('click', () => this.announce());
        this.elements.uploadInput.addEventListener('change', () => this.uploadVideo());
        this.elements.imageUploadInput.addEventListener('change', () => this.uploadImage());
        this.elements.resumeBtn.addEventListener('click', () => this.resume());
        
        // Modal event listeners
        this.elements.cameraSettingsBtn.addEventListener('click', () => this.openCameraModal());
        this.elements.closeModal.addEventListener('click', () => this.closeCameraModal());
        this.elements.cameraModal.addEventListener('click', (e) => {
            if (e.target === this.elements.cameraModal) {
                this.closeCameraModal();
            }
        });

        // Slideshow modal event listeners
        this.elements.closeSlideshowModal.addEventListener('click', () => this.closeSlideshowModal());
        this.elements.slideshowModal.addEventListener('click', (e) => {
            if (e.target === this.elements.slideshowModal) {
                this.closeSlideshowModal();
            }
        });
        this.elements.slideshowForm.addEventListener('submit', (e) => this.handleSlideshowForm(e));
        
        // Form event listeners
        this.elements.addCameraForm.addEventListener('submit', (e) => this.addCamera(e));
        this.elements.credentialForm.addEventListener('submit', (e) => this.addDiscoveredCamera(e));
        
        // Network scanning
        this.elements.scanNetworkBtn.addEventListener('click', () => this.scanNetwork());
        
        // Credential modal
        this.elements.closeCredentialModal.addEventListener('click', () => this.closeCredentialModal());
        this.elements.credentialModal.addEventListener('click', (e) => {
            if (e.target === this.elements.credentialModal) {
                this.closeCredentialModal();
            }
        });
        
        // ESC key to close modals
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                if (this.elements.credentialModal.classList.contains('show')) {
                    this.closeCredentialModal();
                } else if (this.elements.cameraModal.classList.contains('show')) {
                    this.closeCameraModal();
                } else if (this.elements.slideshowModal.classList.contains('show')) {
                    this.closeSlideshowModal();
                }
            }
        });
    }
    
    startStatusChecking() {
        // Her 5 saniyede bir durumu kontrol et
        this.statusCheckInterval = setInterval(() => {
            if (!this.isProcessing) {
                this.checkStatus();
                this.checkSystemInfo();
            }
        }, 5000);
    }

    async checkStatus() {
        try {
            const [statusRes, camRes] = await Promise.all([
                fetch('/status'),
                fetch('/cameras')
            ]);
            const status = await statusRes.json();
            const cams = await camRes.json();
            this.updateUI(status, cams);
        } catch (error) {
            this.handleError('Sunucuya bağlanılamıyor');
        }
    }

    async checkSystemInfo() {
        try {
            const response = await fetch('/system_info');
            const data = await response.json();
            this.elements.cpuTemp.textContent = data.temperature;
            this.elements.diskUsage.textContent = data.disk_usage;
        } catch (error) {
            this.elements.cpuTemp.textContent = 'Hata';
            this.elements.diskUsage.textContent = 'Hata';
        }
    }
    
    updateUI(status, cams) {
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
            (status.source === 'video' ? 'Tanıtım Videosu' : (status.source === 'camera' ? 'Canlı Kamera' : status.source)) :
            'Yok';
        this.elements.lastUpdate.textContent = new Date().toLocaleTimeString('tr-TR');

        // Butonları güncelle
        this.updateButtons(status);
        if (cams && cams.cameras) {
            this.renderCameraList(cams.cameras);
        }
    }
    
    updateButtons(status) {
        if (!this.isProcessing) {
            this.elements.playVideoBtn.disabled = false;
            this.elements.playSlideshowBtn.disabled = false;
            this.elements.announceBtn.disabled = false;
            this.elements.stopBtn.disabled = !status.playing;
            this.elements.resumeBtn.disabled = !status.automation_paused;
            
            // Buton durumlarını güncelle
            this.elements.playVideoBtn.classList.remove('loading');
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

    async playSlideshow(images, interval) {
        if (this.isProcessing) return;
        this.isProcessing = true;
        this.disableAllButtons();
        this.elements.playSlideshowBtn.classList.add('loading');
        this.addLog('Slayt gösterisi isteği gönderiliyor...');

        try {
            const response = await fetch('/play_slideshow', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({images: images, interval: interval})
            });
            const data = await response.json();
            if (data.success) {
                this.addLog('Slayt gösterisi başarıyla başlatıldı', 'success');
                this.updateUI(data.status);
                this.closeSlideshowModal();
            } else {
                this.addLog(`Hata: ${data.message}`, 'error');
            }
        } catch (error) {
            this.handleError('Slayt gösterisi hatası');
        } finally {
            this.isProcessing = false;
            this.elements.playSlideshowBtn.classList.remove('loading');
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

    async loadCameras() {
        try {
            const response = await fetch('/cameras');
            const data = await response.json();
            this.renderCameraList(data.cameras || []);
        } catch (e) {
            this.addLog('Kamera listesi alınamadı', 'error');
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

    async uploadVideo() {
        const files = this.elements.uploadInput.files;
        if (files.length === 0) return;

        this.isProcessing = true;
        this.disableAllButtons();
        this.addLog(`${files.length} video yükleniyor...`);

        const formData = new FormData();
        for (const file of files) {
            formData.append('files[]', file);
        }

        try {
            const res = await fetch('/upload', {method: 'POST', body: formData});
            const data = await res.json();
            if (data.success) {
                this.addLog('Video(lar) başarıyla yüklendi', 'success');
                this.loadVideos();
            } else {
                this.addLog(`Yükleme hatası: ${data.message}`, 'error');
            }
        } catch (e) {
            this.addLog('Yükleme sırasında bir hata oluştu', 'error');
        } finally {
            this.isProcessing = false;
            this.updateButtons({playing:false});
            this.elements.uploadInput.value = ''; // Reset file input
        }
    }

    async uploadImage() {
        const files = this.elements.imageUploadInput.files;
        if (files.length === 0) return;

        this.isProcessing = true;
        this.disableAllButtons();
        this.addLog(`${files.length} görsel yükleniyor...`);

        const formData = new FormData();
        for (const file of files) {
            formData.append('files[]', file);
        }

        try {
            const res = await fetch('/upload_image', {method: 'POST', body: formData});
            const data = await res.json();
            if (data.success) {
                this.addLog('Görsel(ler) başarıyla yüklendi', 'success');
            } else {
                this.addLog(`Yükleme hatası: ${data.message}`, 'error');
            }
        } catch (e) {
            this.addLog('Yükleme sırasında bir hata oluştu', 'error');
        } finally {
            this.isProcessing = false;
            this.updateButtons({playing:false});
            this.elements.imageUploadInput.value = ''; // Reset file input
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
        this.elements.playSlideshowBtn.disabled = true;
        this.elements.stopBtn.disabled = true;
        this.elements.announceBtn.disabled = true;
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

    // Modal Methods
    openCameraModal() {
        this.elements.cameraModal.classList.add('show');
        this.loadModalCameras();
    }

    closeCameraModal() {
        this.elements.cameraModal.classList.remove('show');
        this.elements.addCameraForm.reset();
    }

    async loadModalCameras() {
        try {
            const response = await fetch('/cameras');
            const data = await response.json();
            this.renderModalCameraList(data.cameras || []);
        } catch (e) {
            this.addLog('Modal kamera listesi alınamadı', 'error');
        }
    }

    renderModalCameraList(cameras) {
        if (cameras.length === 0) {
            this.elements.modalCameraList.innerHTML = '<div class="empty-camera-list">Henüz kamera eklenmemiş</div>';
            return;
        }

        this.elements.modalCameraList.innerHTML = '';
        cameras.forEach(camera => {
            const cameraItem = document.createElement('div');
            cameraItem.className = 'modal-camera-item';
            cameraItem.innerHTML = `
                <div class="camera-info">
                    <h5>${camera.name}</h5>
                    <p>${camera.url}</p>
                </div>
                <div class="camera-actions">
                    <button class="delete-btn" onclick="piEkran.deleteCamera('${camera.name}')">
                        Sil
                    </button>
                </div>
            `;
            this.elements.modalCameraList.appendChild(cameraItem);
        });
    }

    async addCamera(event) {
        event.preventDefault();
        const name = this.elements.cameraName.value;
        const url = this.elements.cameraUrl.value;
        if (!name || !url) return;

        try {
            const response = await fetch('/cameras', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({name, url})
            });
            const data = await response.json();
            if (data.success) {
                this.addLog('Kamera eklendi', 'success');
                this.loadModalCameras();
                this.loadCameras();
                this.elements.addCameraForm.reset();
            } else {
                this.addLog('Kamera eklenemedi', 'error');
            }
        } catch (e) {
            this.addLog('Kamera eklenirken hata', 'error');
        }
    }

    async deleteCamera(name) {
        if (!confirm(`'${name}' adlı kamerayı silmek istediğinizden emin misiniz?`)) return;

        try {
            const response = await fetch('/cameras', {
                method: 'DELETE',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({name})
            });
            const data = await response.json();
            if (data.success) {
                this.addLog('Kamera silindi', 'success');
                this.loadModalCameras();
                this.loadCameras();
            } else {
                this.addLog('Kamera silinemedi', 'error');
            }
        } catch (e) {
            this.addLog('Kamera silinirken hata', 'error');
        }
    }

    // Slideshow Modal Methods
    async openSlideshowModal() {
        this.elements.slideshowModal.classList.add('show');
        await this.loadSlideshowImages();
    }

    closeSlideshowModal() {
        this.elements.slideshowModal.classList.remove('show');
    }

    async loadSlideshowImages() {
        try {
            const response = await fetch('/images');
            const data = await response.json();
            this.renderSlideshowImageList(data.images || []);
        } catch (e) {
            this.addLog('Görsel listesi alınamadı', 'error');
        }
    }

    renderSlideshowImageList(images) {
        this.elements.slideshowImageList.innerHTML = '';
        if (images.length === 0) {
            this.elements.slideshowImageList.innerHTML = '<p>Slayt gösterisi için hiç görsel bulunamadı.</p>';
            return;
        }
        images.forEach(image => {
            const label = document.createElement('label');
            label.className = 'video-item';
            const cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.value = image;
            cb.checked = true;
            label.appendChild(cb);
            label.appendChild(document.createTextNode(' ' + image));
            this.elements.slideshowImageList.appendChild(label);
        });
    }

    handleSlideshowForm(event) {
        event.preventDefault();
        const selectedImages = Array.from(this.elements.slideshowImageList.querySelectorAll('input[type="checkbox"]:checked'))
            .map(cb => cb.value);
        const interval = this.elements.slideshowForm.querySelector('#slideshowInterval').value;

        if (selectedImages.length > 0) {
            this.playSlideshow(selectedImages, interval);
        } else {
            this.addLog('Lütfen slayt gösterisi için en az bir görsel seçin.', 'warning');
        }
    }
}

const piEkran = new PiEkranController();
