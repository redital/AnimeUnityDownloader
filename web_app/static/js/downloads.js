/**
 * downloads.js - Gestione dei download e monitoraggio dello stato
 */

/**
 * Aggiorna il progresso di un singolo download
 */
function updateDownloadProgress(anime_id, progressSpan, progressText, cancelBtn) {
  if (completedDownloads.has(anime_id)) {
    return; // Skip se download già completato
  }

  const intervalId = setInterval(async function () {
    try {
      const data = await apiCall(`/download-status/${anime_id}`, 'GET');

      if (data.status === 'success') {
        const info = data.data;
        const animeName = info.anime_name || 'Anime';

        // Limita la percentuale a 100%
        const progressWidth = Math.min((info.overall_percent / 100) * MAX_PROGRESS_WIDTH, MAX_PROGRESS_WIDTH);
        progressSpan.style.width = `${progressWidth}px`;

        // Aggiorna il testo in base allo stato
        if (info.status === 'running') {
          progressText.innerHTML = `<span class="anime-name">${animeName}</span><span class="progress-percent">${Math.min(Math.round(info.overall_percent), 100)}% completato</span>`;
        } else if (info.status === 'paused') {
          progressText.innerHTML = `<span class="anime-name">${animeName}</span><span class="progress-percent">In pausa - ${Math.min(Math.round(info.overall_percent), 100)}%</span>`;
        } else if (info.status === 'completed') {
          progressText.innerHTML = `<span class="anime-name">${animeName}</span><span class="progress-percent">Completato!</span>`;
          progressSpan.style.width = `${MAX_PROGRESS_WIDTH}px`;
          clearInterval(intervalId);
          completedDownloads.add(anime_id);
          updateAllDownloadProgress();
        } else if (info.status === 'failed') {
          progressText.innerHTML = `<span class="anime-name">${animeName}</span><span class="progress-percent">Errore</span>`;
          progressSpan.style.width = `0px`;
          clearInterval(intervalId);
          completedDownloads.add(anime_id);
          updateAllDownloadProgress();
        } else if (info.status === 'cancelled') {
          progressText.innerHTML = `<span class="anime-name">${animeName}</span><span class="progress-percent">Annullato</span>`;
          progressSpan.style.width = `0px`;
          clearInterval(intervalId);
          completedDownloads.add(anime_id);
          updateAllDownloadProgress();
        } else if (info.status === 'queued') {
          progressText.innerHTML = `<span class="anime-name">${animeName}</span><span class="progress-percent">In attesa...</span>`;
          progressSpan.style.width = `0px`;
        }

        // Aggiorna lo stato del pulsante di cancel
        if (cancelBtn) {
          cancelBtn.disabled = info.status === 'completed' || info.status === 'failed' || info.status === 'cancelled';
        }
      }
    } catch (error) {
      console.error(`Errore nel recupero dello stato per ${anime_id}:`, error);
      clearInterval(intervalId);
    }
  }, POLLING_INTERVAL);
}

/**
 * Aggiorna il progresso di tutti i download
 */
async function updateAllDownloadProgress() {
  try {
    const data = await apiCall('/download-statuses', 'GET');

    if (data.status === 'success') {
      const downloads = data.data;
      const progressContainer = document.getElementById('allDownloadProgressContainer');
      if (!progressContainer) return;

      progressContainer.innerHTML = '';

      downloads.forEach(download => {
        const downloadProgress = document.createElement('div');
        downloadProgress.classList.add('download-progress');
        downloadProgress.setAttribute('id', `progress_${download.anime_id}`);

        const progressBar = document.createElement('div');
        progressBar.classList.add('progress-bar');

        const progressSpan = document.createElement('span');
        progressBar.appendChild(progressSpan);

        const progressText = document.createElement('div');
        progressText.classList.add('progress-text');

        // Crea il pulsante di cancel
        const cancelBtn = document.createElement('button');
        cancelBtn.classList.add('cancel-btn', 'danger');
        cancelBtn.textContent = '✕';
        cancelBtn.onclick = async () => {
          if (showConfirm('Vuoi annullare questo download?')) {
            await cancelSingleDownload(download.anime_id);
          }
        };

        downloadProgress.appendChild(progressBar);
        downloadProgress.appendChild(progressText);
        progressText.appendChild(cancelBtn);

        progressContainer.appendChild(downloadProgress);

        if (completedDownloads.has(download.anime_id)) {
          // Download completato/fallito
          if (download.status === 'completed') {
            progressText.innerHTML = `<span class="anime-name">${download.anime_name || 'Anime'}</span><span class="progress-percent">Completato!</span>`;
            progressSpan.style.width = `${MAX_PROGRESS_WIDTH}px`;
          } else if (download.status === 'failed') {
            progressText.innerHTML = `<span class="anime-name">${download.anime_name || 'Anime'}</span><span class="progress-percent">Errore</span>`;
            progressSpan.style.width = `0px`;
          } else if (download.status === 'cancelled') {
            progressText.innerHTML = `<span class="anime-name">${download.anime_name || 'Anime'}</span><span class="progress-percent">Annullato</span>`;
            progressSpan.style.width = `0px`;
          }
          cancelBtn.disabled = true;
          progressText.appendChild(cancelBtn);
        } else if (download.status === 'queued') {
          progressText.innerHTML = `<span class="anime-name">${download.anime_name || 'Anime'}</span><span class="progress-percent">In attesa...</span>`;
          progressSpan.style.width = `0px`;
          cancelBtn.disabled = false;
          progressText.appendChild(cancelBtn);
        } else {
          // Running or paused - inizio il polling
          cancelBtn.disabled = false;
          progressText.appendChild(cancelBtn);
          updateDownloadProgress(download.anime_id, progressSpan, progressText, cancelBtn);
        }
      });
    }
  } catch (error) {
    console.error('Errore nel recupero degli stati dei download:', error);
  }
}

/**
 * Avvia un nuovo download
 */
async function startDownload() {
  const anime_id = document.getElementById('anime_id').value.trim();
  const start_episode = document.getElementById('start_episode').value.trim();
  const end_episode = document.getElementById('end_episode').value.trim();
  const custom_path = document.getElementById('custom_path').value.trim();

  if (!anime_id) {
    showMessage('Inserisci un ID anime valido', 'error');
    return;
  }

  const query = new URLSearchParams();
  if (start_episode) query.append('start_episode', start_episode);
  if (end_episode) query.append('end_episode', end_episode);
  if (custom_path) query.append('custom_path', custom_path);
  
  // Aggiungi parametro 'force' basato sulla modalità manuale
  const forceMode = isManualModeActive && isManualModeActive();
  query.append('force', forceMode ? 'true' : 'false');

  try {
    const data = await apiCall(`/download/${anime_id}?${query.toString()}`, 'GET');

    if (data.status === 'success') {
      showMessage('Download avviato con successo!', 'success');
      document.getElementById('anime_id').value = '';
      document.getElementById('start_episode').value = '';
      document.getElementById('end_episode').value = '';
      updateAllDownloadProgress();
    } else {
      showMessage(`Errore: ${data.message}`, 'error');
    }
  } catch (error) {
    showMessage(`Errore: ${error.message}`, 'error');
  }
}

/**
 * Annulla un singolo download
 */
async function cancelSingleDownload(anime_id) {
  try {
    const result = await apiCall(`/download/${anime_id}/cancel`, 'POST');
    showMessage(result.message || 'Download annullato', 'success');
    await updateAllDownloadProgress();
    await fetchNasStatus();
  } catch (error) {
    showMessage(`Errore: ${error.message}`, 'error');
  }
}

/**
 * Pausa tutti i download
 */
async function pauseAllDownloads() {
  try {
    const result = await apiCall('/downloads/pause', 'POST');
    showMessage(result.message || 'Tutti i download messi in pausa', 'success');
    await updateAllDownloadProgress();
    await fetchNasStatus();
  } catch (error) {
    showMessage(`Errore: ${error.message}`, 'error');
  }
}

/**
 * Riprendi tutti i download
 */
async function resumeAllDownloads() {
  try {
    const result = await apiCall('/downloads/resume', 'POST');
    showMessage(result.message || 'Tutti i download ripresi', 'success');
    await updateAllDownloadProgress();
    await fetchNasStatus();
  } catch (error) {
    showMessage(`Errore: ${error.message}`, 'error');
  }
}

/**
 * Annulla tutti i download
 */
async function cancelAllDownloads() {
  if (!showConfirm('Sei sicuro di voler annullare TUTTI i download?')) return;

  try {
    const result = await apiCall('/downloads/cancel', 'POST');
    showMessage(result.message || 'Tutti i download annullati', 'success');
    await updateAllDownloadProgress();
    await fetchNasStatus();
  } catch (error) {
    showMessage(`Errore: ${error.message}`, 'error');
  }
}

// Inizializza al caricamento della pagina
window.addEventListener('load', () => {
  updateAllDownloadProgress();
  setInterval(updateAllDownloadProgress, 5000); // Aggiorna lista ogni 5 secondi
});
