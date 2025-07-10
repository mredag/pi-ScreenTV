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
            currentSource: document.getElementById('currentSource'),
            systemStatus: document.getElementById('systemStatus'),
            lastUpdate: document.getElementById('lastUpdate'),
            logContainer: document.getElementById('logContainer')
        };
        
        // Event listener'ları ekle
        this.bindEvents();
        
        // Durumu kontrol et
        this.checkStatus();
        
        // Periyodik durum kontrolü başlat
        this.startStatusChecking();
    }
    
    bindEvents() {
        this.elements.playVideoBtn.addEventListener('click', () => this.playVideo());
        this.elements.playCameraBtn.addEventListener('click', () => this.playCamera());
        this.elements.stopBtn.addEventListener('click', () => this.stop());
        this.elements.announceBtn.addEventListener('click', () => this.announce());
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
            const response = await fetch('/status');
            const data = await response.json();
            this.updateUI(data);
        } catch (error) {
            this.handleError('Sunucuya bağlanılamıyor');
        }
    }
    
    updateUI(status) {
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
    }
    
    updateButtons(status) {
        if (!this.isProcessing) {
            this.elements.playVideoBtn.disabled = false;
            this.elements.playCameraBtn.disabled = false;
            this.elements.announceBtn.disabled = false;
            this.elements.stopBtn.disabled = !status.playing;
            
            // Buton durumlarını güncelle
            this.elements.playVideoBtn.classList.remove('loading');
            this.elements.playCameraBtn.classList.remove('loading');
            this.elements.stopBtn.classList.remove('loading');
            this.elements.announceBtn.classList.remove('loading');
        }
    }
    
    async playVideo() {
        if (this.isProcessing) return;
        
        this.isProcessing = true;
        this.disableAllButtons();
        this.elements.playVideoBtn.classList.add('loading');
        this.addLog('Video oynatma isteği gönderiliyor...');
        
        try {
            const response = await fetch('/play_video', { method: 'POST' });
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