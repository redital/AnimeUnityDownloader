import os
import requests

def check_resource_availability(url):
    """Verifica la disponibilità della risorsa al dato URL"""
    res = requests.get(url, timeout=5)
    if res.status_code != 200:
        if res.status_code == 404:
            return False, "Resource not found (404)"
        if res.status_code == 405:
            return False, "Method not allowed (405)"
        return False, f"Error, status code: {res.status_code}"
    return True, "ok"

def create_custom_path(base_path, custom_path):
    """Crea un percorso personalizzato, se necessario"""
    if custom_path:
        return os.path.join(base_path, custom_path)
    return base_path
