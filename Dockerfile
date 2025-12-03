# Immagine base
FROM python:3.11

# Installazione di VLC e altre dipendenze (se non già incluse nel tuo codice)
RUN apt-get update && \
    apt-get install -y iputils-ping nmap && \
    rm -rf /var/lib/apt/lists/*

# Impostazioni di lavoro
WORKDIR /app

# Copia i file necessari
COPY . /app

# Aggiorna pip
RUN pip install --upgrade pip

# Installa le dipendenze
RUN pip install --no-cache-dir -r requirements.txt

# Espone la porta 5000
EXPOSE ${SERVICE_PORT}

# Avvia l'app Flask
CMD ["python", "flask_app.py"]
#CMD ["gunicorn", "-b", "0.0.0.0:5000", "flask_app:app"]
