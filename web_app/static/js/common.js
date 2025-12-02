/**
 * common.js - Utilities e costanti condivise
 */

// ===== CONSTANTS =====
const MAX_PROGRESS_WIDTH = 400;
const POLLING_INTERVAL = 1000; // ms
const NAS_POLLING_INTERVAL = 30 * 1000; // 30 secondi

// ===== SHARED STATE =====
const completedDownloads = new Set();

// ===== UTILITY FUNCTIONS =====

/**
 * Mostra un messaggio di risultato
 */
function showMessage(message, type = 'success') {
  const resultMessage = document.getElementById('resultMessage');
  if (!resultMessage) return;

  resultMessage.textContent = message;
  resultMessage.className = type; // 'success' o 'error'
  resultMessage.style.display = 'block';

  // Auto-hide dopo 5 secondi
  setTimeout(() => {
    resultMessage.style.display = 'none';
  }, 5000);
}

/**
 * Toggle dark mode
 */
function toggleDarkMode() {
  const html = document.documentElement;
  const isDark = html.classList.toggle('dark-mode');
  localStorage.setItem('darkMode', isDark ? 'true' : 'false');
}

/**
 * Carica dark mode dal localStorage
 */
function loadDarkModePreference() {
  const isDark = localStorage.getItem('darkMode') === 'true';
  if (isDark) {
    document.documentElement.classList.add('dark-mode');
  }
}

/**
 * Mostra una conferma
 */
function showConfirm(message) {
  return confirm(message);
}

/**
 * Fetch helper con gestione errori
 */
async function apiCall(url, method = 'GET', body = null) {
  try {
    const options = { method };
    if (body) {
      options.headers = { 'Content-Type': 'application/json' };
      options.body = JSON.stringify(body);
    }

    const response = await fetch(url, options);
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.message || `HTTP ${response.status}`);
    }

    return data;
  } catch (error) {
    console.error(`API error: ${url}`, error);
    throw error;
  }
}

// Carica preferenze al caricamento
window.addEventListener('load', loadDarkModePreference);
