/**
 * nas.js - Gestione dello stato NAS e controlli
 */

/**
 * Recupera lo stato del NAS e aggiorna l'UI
 */
async function fetchNasStatus() {
  try {
    const result = await apiCall('/nas/status', 'GET');

    if (result.status === 'success') {
      const data = result.data;
      updateNasStatusDisplay(data);
      updateNasButtonStates(data);
    }
  } catch (error) {
    console.error('Errore nel recupero dello stato NAS:', error);
  }
}

/**
 * Aggiorna il display dello stato NAS
 */
function updateNasStatusDisplay(data) {
  const container = document.getElementById('nasStatusContainer');
  if (!container) return;

  const onlineText = data.online ? '<span class="status-online">Online</span>' : '<span class="status-offline">Offline</span>';
  const mountText = data.mount_ok ? '<span class="status-online">OK</span>' : '<span class="status-offline">Non OK</span>';

  container.innerHTML = `<strong>NAS:</strong> ${data.host} | <strong>Stato:</strong> ${onlineText} | <strong>Share:</strong> ${mountText}`;
}

/**
 * Aggiorna lo stato dei pulsanti NAS in base allo stato dei download
 */
async function updateNasButtonStates(nasData) {
  try {
    const dlResult = await apiCall('/download-statuses', 'GET');

    let runningOrQueued = 0;
    let pausedCount = 0;

    if (dlResult.status === 'success') {
      dlResult.data.forEach(d => {
        if (d.status === 'running' || d.status === 'queued') runningOrQueued++;
        if (d.status === 'paused') pausedCount++;
      });
    }

    const onBtn = document.getElementById('nasPowerOnBtn');
    const offBtn = document.getElementById('nasPowerOffBtn');
    const remountBtn = document.getElementById('nasRemountBtn');

    // Power on: enabled se NAS è offline
    if (onBtn) onBtn.disabled = nasData.online;

    // Power off: disabled se NAS è offline o ci sono download attivi (a meno che non siano tutti in pausa)
    if (offBtn) offBtn.disabled = (!nasData.online) || (runningOrQueued > 0 && pausedCount === 0);

    // Remount: enabled se NAS è online e mount non OK
    if (remountBtn) remountBtn.disabled = !nasData.online || nasData.mount_ok;
  } catch (error) {
    console.error('Errore nell\'aggiornamento dei pulsanti NAS:', error);
  }
}

/**
 * Accende il NAS
 */
async function nasPowerOn() {
  try {
    const result = await apiCall('/nas/power/on', 'POST');
    showMessage(result.message || 'NAS acceso', 'success');
    await fetchNasStatus();
  } catch (error) {
    showMessage(`Errore: ${error.message}`, 'error');
  }
}

/**
 * Spegne il NAS
 */
async function nasPowerOff() {
  if (!showConfirm('Sei sicuro di voler spegnere il NAS?')) return;

  try {
    const result = await apiCall('/nas/power/off', 'POST');
    showMessage(result.message || 'NAS spento', 'success');
    await fetchNasStatus();
  } catch (error) {
    showMessage(`Errore: ${error.message}`, 'error');
  }
}

/**
 * Ripara la share del NAS
 */
async function nasRemount() {
  try {
    const result = await apiCall('/nas/remount', 'POST');
    showMessage(result.message || 'Share riparata', 'success');
    await fetchNasStatus();
  } catch (error) {
    showMessage(`Errore: ${error.message}`, 'error');
  }
}

// Inizializza il monitoraggio NAS al caricamento della pagina
window.addEventListener('load', () => {
  if (document.getElementById('nasStatusContainer')) {
    fetchNasStatus();
    setInterval(fetchNasStatus, NAS_POLLING_INTERVAL);
  }
});
