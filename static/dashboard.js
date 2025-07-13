document.addEventListener('DOMContentLoaded', () => {
    const sidebar = document.getElementById('sidebar');
    const toggle = document.getElementById('sidebarToggle');

    // Sidebar toggle
    if (toggle) {
        toggle.addEventListener('click', () => {
            if (window.innerWidth <= 768) {
                sidebar.classList.toggle('open');
            } else {
                sidebar.classList.toggle('collapsed');
            }
        });
    }

    // System Status & Logs
    const systemStatusWidget = document.getElementById('systemStatusWidget');
    const logModal = document.getElementById('logModal');
    const closeLogModal = document.getElementById('closeLogModal');
    const logContent = document.getElementById('logContent');

    if (systemStatusWidget) {
        systemStatusWidget.addEventListener('click', () => {
            logModal.style.display = 'block';
            fetchLogs();
        });
    }

    if (closeLogModal) {
        closeLogModal.addEventListener('click', () => {
            logModal.style.display = 'none';
        });
    }

    // Close modal on outside click
    window.addEventListener('click', (event) => {
        if (event.target == logModal) {
            logModal.style.display = 'none';
        }
    });

    const fetchSystemInfo = async () => {
        try {
            const response = await fetch('/system_info');
            const data = await response.json();

            // Update widget
            document.getElementById('cpuUsageWidget').textContent = `${data.cpu_usage}%`;
            document.getElementById('ramUsageWidget').textContent = `${data.memory.percent}%`;
            document.getElementById('tempWidget').textContent = `${data.temperature}`;

            // Update system info page
            document.getElementById('cpuTemp').textContent = data.temperature;
            document.getElementById('diskUsage').textContent = data.disk_usage;
            // You can add more detailed info here if you have elements for it
            
        } catch (error) {
            console.error('Error fetching system info:', error);
        }
    };

    const fetchLogs = async () => {
        try {
            const response = await fetch('/logs');
            const data = await response.json();
            if (data.success) {
                logContent.textContent = data.logs;
            } else {
                logContent.textContent = `Loglar alınamadı: ${data.logs}`;
            }
        } catch (error) {
            console.error('Error fetching logs:', error);
            logContent.textContent = 'Loglar alınırken bir hata oluştu.';
        }
    };

    // Initial fetch and periodic update
    fetchSystemInfo();
    setInterval(fetchSystemInfo, 5000); // Update every 5 seconds
});
