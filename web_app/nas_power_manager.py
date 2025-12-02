import time
from nas_power import NASPowerManager
from logger import logger
from config import (
    nas_mac_address,
    nas_host_name,
    omv_user,
    omv_password,
    mount_path,
    ssh_host,
    ssh_user,
    ssh_password,
)

# Inizializza il manager del NAS con i valori di configurazione
nas_manager = NASPowerManager(
    mac_address=nas_mac_address,
    omv_user=omv_user,
    omv_password=omv_password,
    omv_host=nas_host_name,
    nas_ip=nas_host_name,
    mount_path=mount_path,
    ssh_host=ssh_host,
    ssh_user=ssh_user,
    ssh_password=ssh_password,
)

# --- NAS control API helpers --------------------------------------------
def get_nas_status():
    """Restituisce lo stato di online/offline e della mount share."""
    
    try:
        online, mount_ok = nas_manager.get_nas_status()
    except Exception as e:
        logger.exception("Errore nel recupero dello stato del NAS:")
        return {"status": "error", "message": str(e)}, 503
    
    data = {
        "online": bool(online),
        "mount_ok": bool(mount_ok),
        "host": nas_manager.omv_host,
        "mount_path": nas_manager.mount_path,
    }
    return {"status": "success", "data": data}, 200



def nas_power_on_only():
    try:
        logger.warning("NAS offline. Procedo all'accensione.")
        nas_manager.power_on()
        logger.info("Attendo 60 secondi per il NAS per avviarsi...")
        time.sleep(60)
        logger.info("Sono passati 60 secondi, ricontrollo lo stato del NAS.")
        nas_online = nas_manager.is_nas_online()
        logger.info(f"NAS status after power on - Online: {nas_online}")

        if nas_online: 
            return {"status": "success", "message": "Wake-on-LAN inviato"}, 200
        else: 
            msg = "Accensione del NAS fallita."
            logger.error(msg)
            return {"status": "error", "message": msg}, 500
    except Exception as e:
        logger.exception("Errore durante power_on:")
        return {"status": "error", "message": str(e)}, 500
    
def nas_power_on(nas_online, mount_ok):
    def power_on_failure():
        msg = "Accensione del NAS fallita.\nStato NAS: {}\nStato mount: {}".format(nas_online, mount_ok)
        logger.error(msg)
        return {"status": "error", "message": msg}, 500
    try:
        if not nas_online:
            n = 4
            for i in range(n):
                logger.info(f"Tentativo di accensione {i+1}/{n}")
                res = nas_power_on_only()
                if res[1] == 200:
                    break
            if res[1] != 200:
                return res
        
        
        if not mount_ok:
            logger.warning("Cartella condivisa non raggiungibile. Procedo alla riparazione.")
            nas_manager.remount_share_via_ssh()

        nas_online, mount_ok = nas_manager.get_nas_status()
        if not nas_online or not mount_ok:
            return power_on_failure()
        return {"status": "success", "message": "NAS online e mount OK"}, 200

        
    except Exception as e:
        logger.exception("Errore durante power_on:")
        return {"status": "error", "message": str(e)}, 500
    



def nas_power_off():
    try:
        ok = nas_manager.power_off()
        if ok:
            return {"status": "success", "message": "Shutdown inviato"}, 200
        return {"status": "error", "message": "Shutdown fallito"}, 500
    except Exception as e:
        logger.exception("Errore durante power_off:")
        return {"status": "error", "message": str(e)}, 500


def nas_remount():
    try:
        ok = nas_manager.remount_share_via_ssh()
        if ok:
            return {"status": "success", "message": "Remount eseguito"}, 200
        return {"status": "error", "message": "Remount fallito"}, 500
    except Exception as e:
        logger.exception("Errore durante remount:")
        return {"status": "error", "message": str(e)}, 500