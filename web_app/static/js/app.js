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

    // Chiamata al server per avviare il download — ORA CORRETTA
    fetch(`/download/${anime_id}?${query.toString()}`, {
        method: 'GET'
    })
    .then(response => response.json())
    .then(data => {
        const resultMessage = document.getElementById('resultMessage');

        if (data.status === 'success') {
            resultMessage.textContent = 'Download avviato con successo!';
            resultMessage.style.color = 'green';

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

function updateDownloadProgress(anime_id) {
    setInterval(function() {
        fetch(`/download-status/${anime_id}`)
        .then(response => response.json())
        .then(data => {
            const progressContainer = document.getElementById('downloadProgressContainer');
            progressContainer.innerHTML = '';

            if (data.status === 'success') {
                const info = data.data;
                const progress = document.createElement('div');
                progress.classList.add('progress-bar');
                const progressBar = document.createElement('span');
                progressBar.style.width = `${info.overall_percent * 100}%`;
                progress.appendChild(progressBar);
                progressContainer.appendChild(progress);
            }
        });
    }, 2000);
}
