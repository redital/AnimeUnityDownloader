// Costante per la larghezza massima della barra di progresso
const MAX_PROGRESS_WIDTH = 400;
const POLLING_INTERVAL = 1000; // Aggiornamento ogni 1 secondo

// Funzione generica per aggiornare il progresso di un download
function updateDownloadProgress(anime_id, progressSpan, progressText) {
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
                        clearInterval(intervalId);
                    } else if (info.status === 'failed') {
                        progressText.textContent = `${animeName}: Download fallito.`;
                        clearInterval(intervalId);
                    } else if (info.status === 'queued') {
                        progressText.textContent = `${animeName}: In attesa...`;
                    }
                }
            })
            .catch(error => {
                console.error(`Errore nel recupero dello stato per ${anime_id}:`, error);
                clearInterval(intervalId);
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

                    // Avvia il monitoraggio per tutti i download (sia running che completed/failed/queued)
                    updateDownloadProgress(download.anime_id, progressSpan, progressText);
                });
            }
        })
        .catch(error => console.error('Errore nel recupero degli stati dei download:', error));
}

// Inizializza tutti i progressi al caricamento della pagina
window.addEventListener('load', () => {
    updateAllDownloadProgress();
});
