// Costante per la larghezza massima della barra di progresso
const MAX_PROGRESS_WIDTH = 400;
const POLLING_INTERVAL = 1000; // Aggiornamento ogni 1 secondo

// Aggiungiamo un oggetto per tracciare i task già completati (per evitare il polling)
const completedDownloads = new Set(); // Set per tracciare gli ID dei download completati

// Funzione generica per aggiornare il progresso di un download
function updateDownloadProgress(anime_id, progressSpan, progressText) {
    // Verifica se questo download è già stato completato o fallito
    if (completedDownloads.has(anime_id)) {
        return; // Esci dalla funzione se il download è già stato completato
    }

    const intervalId = setInterval(function() {
        fetch(`/download-status/${anime_id}`)
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    const info = data.data;
                    const animeName = info.anime_name || 'Anime';

                    // Limitiamo la percentuale a 100%
                    const progressWidth = Math.min((info.overall_percent / 100) * MAX_PROGRESS_WIDTH, MAX_PROGRESS_WIDTH);
                    progressSpan.style.width = `${progressWidth}px`;

                    // Mostriamo il nome dell'anime e la percentuale
                    if (info.status === 'running') {
                        progressText.textContent = `${animeName}: ${Math.min(Math.round(info.overall_percent), 100)}% completato`;
                    } else if (info.status === 'completed') {
                        progressText.textContent = `${animeName}: Download completato!`;
                        progressSpan.style.width = `${MAX_PROGRESS_WIDTH}px`; // La barra è piena
                        clearInterval(intervalId); // Ferma il polling
                        completedDownloads.add(anime_id); // Aggiungi l'ID al set dei completati
                        updateAllDownloadProgress(); // Ricarica la lista per verificare il prossimo download
                    } else if (info.status === 'failed') {
                        progressText.textContent = `${animeName}: Download fallito.`;
                        progressSpan.style.width = `0px`; // La barra è vuota
                        clearInterval(intervalId); // Ferma il polling
                        completedDownloads.add(anime_id); // Aggiungi l'ID al set dei falliti
                        updateAllDownloadProgress(); // Ricarica la lista per verificare il prossimo download
                    } else if (info.status === 'queued') {
                        progressText.textContent = `${animeName}: In attesa...`;
                        progressSpan.style.width = `0px`; // La barra rimane vuota per "queued"
                    }
                }
            })
            .catch(error => {
                console.error(`Errore nel recupero dello stato per ${anime_id}:`, error);
                clearInterval(intervalId); // Ferma il polling in caso di errore
            });
    }, POLLING_INTERVAL);
}

document.getElementById('toggleParamsBtn').addEventListener('click', function() {
    const paramsDiv = document.getElementById('additionalParams');
    paramsDiv.classList.toggle('hidden');
});

document.getElementById('startDownloadBtn').addEventListener('click', function() {
    const anime_id = document.getElementById('anime_id').value;
    const start_episode = document.getElementById('start_episode').value;
    const end_episode = document.getElementById('end_episode').value;
    const custom_path = document.getElementById('custom_path').value;

    // Costruzione dei query params per GET
    const query = new URLSearchParams();

    if (start_episode) query.append("start_episode", start_episode);
    if (end_episode) query.append("end_episode", end_episode);
    if (custom_path) query.append("custom_path", custom_path);

    // Chiamata al server per avviare il download
    fetch(`/download/${anime_id}?${query.toString()}`, {
        method: 'GET'
    })
        .then(response => response.json())
        .then(data => {
            const resultMessage = document.getElementById('resultMessage');

            if (data.status === 'success') {
                resultMessage.textContent = 'Download avviato con successo!';
                resultMessage.style.color = 'green';

                // Aggiorna la lista dei progressi
                updateAllDownloadProgress();

                // Dopo il successo, svuotiamo tutti i campi tranne custom_path
                document.getElementById('anime_id').value = '';
                document.getElementById('start_episode').value = '';
                document.getElementById('end_episode').value = '';
            } else {
                resultMessage.textContent = `Errore: ${data.message}`;
                resultMessage.style.color = 'red';
            }

            resultMessage.style.display = 'block';
        })
        .catch(error => {
            const resultMessage = document.getElementById('resultMessage');
            resultMessage.textContent = `Errore di rete: ${error.message}`;
            resultMessage.style.color = 'red';
            resultMessage.style.display = 'block';
        });
});

// Funzione per aggiornare il progresso di tutti i download
function updateAllDownloadProgress() {
    // Recupera lo stato di tutti i download in corso
    fetch('/download-statuses')
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                const downloads = data.data;
                const progressContainer = document.getElementById('allDownloadProgressContainer');
                progressContainer.innerHTML = '';  // Pulisce la lista dei download

                // Per ogni download in corso, crea una barra di progresso
                downloads.forEach(download => {
                    // Non creare il monitoraggio per i task completati o falliti
                    if (completedDownloads.has(download.anime_id)) {
                        // Mostra solo il risultato senza eseguire il polling
                        const downloadProgress = document.createElement('div');
                        downloadProgress.classList.add('download-progress');
                        downloadProgress.setAttribute('id', `progress_${download.anime_id}`);
                        progressContainer.appendChild(downloadProgress);

                        const progressBar = document.createElement('div');
                        progressBar.classList.add('progress-bar');
                        downloadProgress.appendChild(progressBar);

                        const progressSpan = document.createElement('span');
                        progressBar.appendChild(progressSpan);

                        const progressText = document.createElement('div');
                        progressText.classList.add('progress-text');
                        downloadProgress.appendChild(progressText);

                        // Se il download è stato completato o fallito, lo mostriamo senza polling
                        if (download.status === 'completed') {
                            progressText.textContent = `${download.anime_name || 'Anime'}: Download completato!`;
                            progressSpan.style.width = `${MAX_PROGRESS_WIDTH}px`; // Barra piena
                        } else if (download.status === 'failed') {
                            progressText.textContent = `${download.anime_name || 'Anime'}: Download fallito.`;
                            progressSpan.style.width = `0px`; // Barra vuota
                        }

                    } else {
                        // Se il download è "queued", non avviamo il monitoraggio, ma solo la visualizzazione
                        const downloadProgress = document.createElement('div');
                        downloadProgress.classList.add('download-progress');
                        downloadProgress.setAttribute('id', `progress_${download.anime_id}`);
                        progressContainer.appendChild(downloadProgress);

                        const progressBar = document.createElement('div');
                        progressBar.classList.add('progress-bar');
                        downloadProgress.appendChild(progressBar);

                        const progressSpan = document.createElement('span');
                        progressBar.appendChild(progressSpan);

                        const progressText = document.createElement('div');
                        progressText.classList.add('progress-text');
                        downloadProgress.appendChild(progressText);

                        if (download.status === 'queued') {
                            progressText.textContent = `${download.anime_name || 'Anime'}: In attesa...`;
                            progressSpan.style.width = `0px`; // La barra rimane vuota per "queued"
                        } else {
                            updateDownloadProgress(download.anime_id, progressSpan, progressText);
                        }
                    }
                });
            }
        })
        .catch(error => console.error('Errore nel recupero degli stati dei download:', error));
}

// Inizializza tutti i progressi al caricamento della pagina
window.addEventListener('load', () => {
    updateAllDownloadProgress();
    // Avvia monitoraggio stato NAS
    if (document.getElementById('nasStatusContainer')) {
        fetchNasStatus();
        setInterval(fetchNasStatus, 30*1000); // ogni 30 secondi
    }
});


// --- NAS UI and controls ------------------------------------------------
function fetchNasStatus() {
    fetch('/nas/status')
        .then(r => r.json())
        .then(result => {
            if (result.status === 'success') {
                const data = result.data;
                const container = document.getElementById('nasStatusContainer');
                if (!container) return;
                        container.textContent = `NAS: ${data.host} — Online: ${data.online ? 'Yes' : 'No'} — Share OK: ${data.mount_ok ? 'Yes' : 'No'}`;

                        const onBtn = document.getElementById('nasPowerOnBtn');
                        const offBtn = document.getElementById('nasPowerOffBtn');
                        const remountBtn = document.getElementById('nasRemountBtn');
                        const pauseAllBtn = document.getElementById('pauseAllBtn');
                        const resumeAllBtn = document.getElementById('resumeAllBtn');
                        const cancelAllBtn = document.getElementById('cancelAllBtn');

                        // Determine download activity to decide button states
                        fetch('/download-statuses')
                            .then(r => r.json())
                            .then(dlres => {
                                let runningOrQueued = 0;
                                let pausedCount = 0;
                                if (dlres.status === 'success') {
                                    dlres.data.forEach(d => {
                                        if (d.status === 'running' || d.status === 'queued') runningOrQueued++;
                                        if (d.status === 'paused') pausedCount++;
                                    });
                                }

                                // NAS power on: only enabled when NAS is offline
                                if (onBtn) onBtn.disabled = data.online;

                                // NAS power off: disabled if NAS offline or there are active downloads (unless all paused)
                                if (offBtn) offBtn.disabled = (!data.online) || (runningOrQueued > 0 && pausedCount === 0);

                                // remount only if mount is not ok AND NAS is online
                                // If NAS is offline, remount makes no sense so keep it disabled
                                if (remountBtn) remountBtn.disabled = data.mount_ok || !data.online;

                                // Pause all: enabled if there are running or queued downloads
                                if (pauseAllBtn) pauseAllBtn.disabled = (runningOrQueued === 0);

                                // Resume all: enabled if there are paused downloads and NAS is up and mount ok
                                if (resumeAllBtn) resumeAllBtn.disabled = !(pausedCount > 0 && data.online && data.mount_ok);

                                // Cancel all: enabled if any active/paused/queued downloads
                                if (cancelAllBtn) cancelAllBtn.disabled = (runningOrQueued === 0 && pausedCount === 0);
                            })
                            .catch(err => console.error('Errore nel recupero degli stati dei download:', err));
            }
        })
        .catch(err => console.error('Impossibile recuperare stato NAS:', err));
}

function notEnabledIfFalse(x) { return !x; }

// Attach button handlers if present
document.addEventListener('click', function(e) {
    if (!e.target) return;
    if (e.target.id === 'nasPowerOnBtn') {
        fetch('/nas/power/on', { method: 'POST' })
            .then(r => r.json()).then(res => { alert(res.message || JSON.stringify(res)); fetchNasStatus(); });
    }
    if (e.target.id === 'nasPowerOffBtn') {
        fetch('/nas/power/off', { method: 'POST' })
            .then(r => r.json()).then(res => { alert(res.message || JSON.stringify(res)); fetchNasStatus(); });
    }
    if (e.target.id === 'nasRemountBtn') {
        fetch('/nas/remount', { method: 'POST' })
            .then(r => r.json()).then(res => { alert(res.message || JSON.stringify(res)); fetchNasStatus(); });
    }

    // Global download controls
    if (e.target.id === 'pauseAllBtn') {
        fetch('/downloads/pause', { method: 'POST' })
            .then(r => r.json())
            .then(res => { alert(res.message || JSON.stringify(res)); updateAllDownloadProgress(); fetchNasStatus(); });
    }
    if (e.target.id === 'resumeAllBtn') {
        fetch('/downloads/resume', { method: 'POST' })
            .then(r => r.json())
            .then(res => { alert(res.message || JSON.stringify(res)); updateAllDownloadProgress(); fetchNasStatus(); });
    }
    if (e.target.id === 'cancelAllBtn') {
        if (!confirm('Sei sicuro di voler annullare tutti i download in corso?')) return;
        fetch('/downloads/cancel', { method: 'POST' })
            .then(r => r.json())
            .then(res => { alert(res.message || JSON.stringify(res)); updateAllDownloadProgress(); fetchNasStatus(); });
    }
});
