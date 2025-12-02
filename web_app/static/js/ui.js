/**
 * ui.js - Gestione degli eventi UI e collegamento dei pulsanti
 */

/**
 * Inizializza gli event listener dei pulsanti
 */
function initializeEventListeners() {
  // Toggle parametri aggiuntivi
  const toggleParamsBtn = document.getElementById('toggleParamsBtn');
  if (toggleParamsBtn) {
    toggleParamsBtn.addEventListener('click', () => {
      const paramsDiv = document.getElementById('additionalParams');
      paramsDiv.classList.toggle('hidden');
    });
  }

  // Avvia download
  const startDownloadBtn = document.getElementById('startDownloadBtn');
  if (startDownloadBtn) {
    startDownloadBtn.addEventListener('click', startDownload);
  }

  // Dark mode toggle
  const darkModeToggle = document.getElementById('darkModeToggle');
  if (darkModeToggle) {
    darkModeToggle.addEventListener('click', toggleDarkMode);
  }

  // NAS buttons
  const nasPowerOnBtn = document.getElementById('nasPowerOnBtn');
  if (nasPowerOnBtn) nasPowerOnBtn.addEventListener('click', nasPowerOn);

  const nasPowerOffBtn = document.getElementById('nasPowerOffBtn');
  if (nasPowerOffBtn) nasPowerOffBtn.addEventListener('click', nasPowerOff);

  const nasRemountBtn = document.getElementById('nasRemountBtn');
  if (nasRemountBtn) nasRemountBtn.addEventListener('click', nasRemount);

  // Download control buttons
  const pauseAllBtn = document.getElementById('pauseAllBtn');
  if (pauseAllBtn) pauseAllBtn.addEventListener('click', pauseAllDownloads);

  const resumeAllBtn = document.getElementById('resumeAllBtn');
  if (resumeAllBtn) resumeAllBtn.addEventListener('click', resumeAllDownloads);

  const cancelAllBtn = document.getElementById('cancelAllBtn');
  if (cancelAllBtn) cancelAllBtn.addEventListener('click', cancelAllDownloads);
}

// Inizializza gli event listener al caricamento della pagina
window.addEventListener('load', initializeEventListeners);
