/**
 * downloads.js - Gestione dei download e monitoraggio dello stato
 */

/**
 * Titolo di un download: nome dell'anime, con gli episodi se non sono tutti
 */
function jobTitle(download) {
  const name = download.anime_name || 'Anime';
  const label = (download.job_id || '').split(':').slice(1).join(':');
  return label && label !== 'all' ? `${name} (ep. ${label})` : name;
}

/**
 * Aggiorna il progresso di un singolo download
 */
function updateDownloadProgress(anime_id, progressSpan, progressText, cancelBtn) {
  if (completedDownloads.has(anime_id)) {
    return; // Skip se download già completato
  }

  const intervalId = setInterval(async function () {
    try {
      const data = await apiCall(`/download-status/${encodeURIComponent(anime_id)}`, 'GET', null, false); // Senza spinner

      if (data.status === 'success') {
        const info = data.data;
        const animeName = info.anime_name || 'Anime';

        // Aggiorna la barra in-place con transizione smooth
        const percentValue = Math.min(Math.round(info.overall_percent), 100);
        const progressPercent = (percentValue / 100) * 100; // Percentuale per width
        progressSpan.style.width = `${progressPercent}%`;

        // Aggiorna il testo in base allo stato
        if (info.status === 'running') {
          progressText.innerHTML = `<span class="anime-name">${animeName}</span><span class="progress-percent">${percentValue}% completato</span>`;
        } else if (info.status === 'paused') {
          progressText.innerHTML = `<span class="anime-name">${animeName}</span><span class="progress-percent">In pausa - ${percentValue}%</span>`;
        } else if (info.status === 'completed') {
          progressText.innerHTML = `<span class="anime-name">${animeName}</span><span class="progress-percent">Completato!</span>`;
          progressSpan.classList.add('final-state');
          progressSpan.style.width = '100%';
          clearInterval(intervalId);
          completedDownloads.add(anime_id);
          await updateAllDownloadProgress();
        } else if (info.status === 'failed') {
          progressText.innerHTML = `<span class="anime-name">${animeName}</span><span class="progress-percent">Errore</span>`;
          progressSpan.classList.add('final-state');
          progressSpan.style.width = '0px';
          clearInterval(intervalId);
          completedDownloads.add(anime_id);
          await updateAllDownloadProgress();
        } else if (info.status === 'cancelled') {
          progressText.innerHTML = `<span class="anime-name">${animeName}</span><span class="progress-percent">Annullato</span>`;
          progressSpan.classList.add('final-state');
          progressSpan.style.width = '0px';
          clearInterval(intervalId);
          completedDownloads.add(anime_id);
          await updateAllDownloadProgress();
        } else if (info.status === 'queued') {
          progressText.innerHTML = `<span class="anime-name">${animeName}</span><span class="progress-percent">In attesa...</span>`;
          progressSpan.style.width = '0px';
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
    const data = await apiCall('/download-statuses', 'GET', null, false); // Senza spinner durante refresh periodici

    if (data.status === 'success') {
      const downloads = data.data;
      const progressContainer = document.getElementById('allDownloadProgressContainer');
      if (!progressContainer) return;

      // Mantieni gli elementi esistenti per evitare flicker
      // Calcola quali anime_id sono presenti nel container
      const existingElements = {};
      progressContainer.querySelectorAll('[data-anime-id]').forEach(el => {
        const animeId = el.getAttribute('data-anime-id');
        existingElements[animeId] = el;
      });

      // Processa ogni download
      downloads.forEach(download => {
        let downloadProgress = existingElements[download.job_id];
        
        // Se non esiste, crealo
        if (!downloadProgress) {
          downloadProgress = document.createElement('div');
          downloadProgress.classList.add('download-progress');
          downloadProgress.setAttribute('data-anime-id', download.job_id);

          const progressBar = document.createElement('div');
          progressBar.classList.add('progress-bar');

          const progressSpan = document.createElement('span');
          progressBar.appendChild(progressSpan);

          const progressText = document.createElement('div');
          progressText.classList.add('progress-text');

          const cancelBtn = document.createElement('button');
          cancelBtn.classList.add('cancel-btn', 'danger');
          cancelBtn.textContent = '✕';
          cancelBtn.setAttribute('data-anime-id', download.job_id);
          cancelBtn.onclick = async function() {
            const animeId = this.getAttribute('data-anime-id');
            const status = downloadProgress.getAttribute('data-status');
            
            if (status === 'running' || status === 'queued' || status === 'paused') {
              if (showConfirm('Vuoi annullare questo download?')) {
                await cancelSingleDownload(animeId);
              }
            } else {
              if (showConfirm('Rimuovere questo task dalla lista?')) {
                await removeSingleTask(animeId);
              }
            }
          };

          downloadProgress.appendChild(progressBar);
          downloadProgress.appendChild(progressText);
          downloadProgress.appendChild(cancelBtn);

          progressContainer.appendChild(downloadProgress);
          delete existingElements[download.job_id];
        }

        // Aggiorna lo stato del download in-place
        const progressBar = downloadProgress.querySelector('.progress-bar');
        const progressSpan = progressBar.querySelector('span');
        const progressText = downloadProgress.querySelector('.progress-text');
        const cancelBtn = downloadProgress.querySelector('.cancel-btn');

        // Mantieni i colori: non ricreate la barra
        const statusAttr = downloadProgress.getAttribute('data-status');
        downloadProgress.setAttribute('data-status', download.status);

        // Aggiorna il contenuto della barra e del testo
        if (completedDownloads.has(download.job_id)) {
          // Download completato/fallito
          if (download.status === 'completed') {
            progressText.innerHTML = `<span class="anime-name">${jobTitle(download)}</span><span class="progress-percent">Completato!</span>`;
            if (!progressSpan.classList.contains('final-state')) {
              progressSpan.classList.add('final-state');
            }
            progressSpan.style.width = '100%';
          } else if (download.status === 'failed') {
            progressText.innerHTML = `<span class="anime-name">${jobTitle(download)}</span><span class="progress-percent">Errore</span>`;
            progressSpan.classList.add('final-state');
            progressSpan.style.width = '0px';
          } else if (download.status === 'cancelled') {
            progressText.innerHTML = `<span class="anime-name">${jobTitle(download)}</span><span class="progress-percent">Annullato</span>`;
            progressSpan.classList.add('final-state');
            progressSpan.style.width = '0px';
          }
          cancelBtn.disabled = false; // Permetti rimozione
        } else if (download.status === 'queued') {
          progressText.innerHTML = `<span class="anime-name">${jobTitle(download)}</span><span class="progress-percent">In attesa...</span>`;
          progressSpan.style.width = '0px';
          cancelBtn.disabled = false;
        } else if (download.status === 'running' || download.status === 'paused') {
          // Aggiorna il progresso tramite polling continuo
          cancelBtn.disabled = false;
          updateDownloadProgress(download.job_id, progressSpan, progressText, cancelBtn);
        }
      });

      // Rimuovi gli elementi per anime che non sono più nella lista
      Object.values(existingElements).forEach(el => el.remove());
    }
  } catch (error) {
    console.error('Errore nel recupero degli stati dei download:', error);
  }
}


/**
 * Rimuove un singolo task (solo se è terminato / fallito / annullato)
 */
async function removeSingleTask(anime_id) {
  try {
    const res = await apiCall(`/download/${encodeURIComponent(anime_id)}/remove`, 'POST', null, true, 'Rimuovendo task...');
    showMessage(res.message || 'Task rimosso', 'success');
    await updateAllDownloadProgress(); // Attendi il refresh immediato della lista
  } catch (error) {
    showMessage(`Errore: ${error.message}`, 'error');
  }
}


/**
 * Pulisce tutti i task completati/falliti/annullati
 */
async function clearFinishedTasks() {
  if (!showConfirm('Vuoi rimuovere tutti i task completati/annullati/errore dalla lista?')) return;
  try {
    const res = await apiCall('/downloads/cleanup', 'POST', null, true, 'Pulendo la lista...');
    showMessage(res.message || 'Lista ripulita', 'success');
    await updateAllDownloadProgress();
  } catch (error) {
    showMessage(`Errore: ${error.message}`, 'error');
  }
}

/**
 * Avvia un nuovo download
 */
async function startDownload() {
  const anime_id = document.getElementById('anime_id').value.trim();
  const start_episode = document.getElementById('start_episode').value.trim();
  const end_episode = document.getElementById('end_episode').value.trim();
  const episodes = document.getElementById('episodes').value.trim();
  const custom_path = document.getElementById('custom_path').value.trim();

  if (!anime_id) {
    showMessage('Inserisci un ID anime valido', 'error');
    return;
  }

  const query = new URLSearchParams();
  if (start_episode) query.append('start_episode', start_episode);
  if (end_episode) query.append('end_episode', end_episode);
  if (episodes) query.append('episodes', episodes);
  if (custom_path) query.append('custom_path', custom_path);

  try {
    const data = await apiCall(`/download/${anime_id}?${query.toString()}`, 'GET', null, true, 'Avviando download...');

    if (data.status === 'success') {
      showMessage('Download avviato con successo!', 'success');
      document.getElementById('anime_id').value = '';
      document.getElementById('start_episode').value = '';
      document.getElementById('end_episode').value = '';
      document.getElementById('episodes').value = '';
      await updateAllDownloadProgress(); // Attendi il refresh immediato della lista
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
    const result = await apiCall(`/download/${encodeURIComponent(anime_id)}/cancel`, 'POST', null, true, 'Annullando download...');
    showMessage(result.message || 'Download annullato', 'success');
    await updateAllDownloadProgress();
  } catch (error) {
    showMessage(`Errore: ${error.message}`, 'error');
  }
}

/**
 * Pausa tutti i download
 */
async function pauseAllDownloads() {
  try {
    const result = await apiCall('/downloads/pause', 'POST', null, true, 'Mettendo in pausa i download...');
    showMessage(result.message || 'Tutti i download messi in pausa', 'success');
    await updateAllDownloadProgress();
  } catch (error) {
    showMessage(`Errore: ${error.message}`, 'error');
  }
}

/**
 * Riprendi tutti i download
 */
async function resumeAllDownloads() {
  try {
    const result = await apiCall('/downloads/resume', 'POST', null, true, 'Riprendendo i download...');
    showMessage(result.message || 'Tutti i download ripresi', 'success');
    await updateAllDownloadProgress();
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
    const result = await apiCall('/downloads/cancel', 'POST', null, true, 'Annullando tutti i download...');
    showMessage(result.message || 'Tutti i download annullati', 'success');
    await updateAllDownloadProgress();
  } catch (error) {
    showMessage(`Errore: ${error.message}`, 'error');
  }
}

// Inizializza al caricamento della pagina
window.addEventListener('load', () => {
  updateAllDownloadProgress();
  setInterval(updateAllDownloadProgress, 3000); // Aggiorna lista ogni 3 secondi (più frequente)
});
