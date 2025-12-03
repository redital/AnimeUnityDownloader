import socket
import requests
import os
import platform
from logger import logger
import paramiko

class NASPowerManager:
    """
    Gestisce accensione (Wake-on-LAN), spegnimento (OMV API), ping, controllo e remount della share.
    """

    def __init__(
        self,
        mac_address: str,
        omv_user: str,
        omv_password: str,
        omv_host: str,
        mount_path: str = None,
        ssh_host: str = None,
        ssh_user: str = None,
        ssh_password: str = None,
    ):
        """
        :param mac_address: MAC address del NAS (formato XX:XX:XX:XX:XX:XX)
        :param omv_user: Username admin OMV
        :param omv_password: Password OMV
        :param omv_host: Hostname o IP OMV (es: 192.168.1.100)
        :param mount_path: Path della cartella montata (opzionale)
        :param ssh_host: Hostname o IP dell'host su cui eseguire il remount via SSH (opzionale)
        :param ssh_user: Username SSH per l'host (opzionale)
        :param ssh_password: Password SSH per l'host (opzionale)
        """
        self.mac_address = mac_address
        self.omv_user = omv_user
        self.omv_password = omv_password
        self.omv_host = omv_host
        self.mount_path = mount_path
        self.ssh_host = ssh_host
        self.ssh_user = ssh_user
        self.ssh_password = ssh_password

    # --- POWER ON ---

    def power_on(self) -> bool:
        """
        Accende il NAS via Wake-on-LAN.
        """
        try:
            self._wake_on_lan()
            logger.info("Wake-on-LAN inviato al NAS.")
            return True
        except Exception as e:
            logger.error(f"Wake-on-LAN fallito: {e}")
            return False

    def _wake_on_lan(self):
        """
        Invia il magic packet Wake-on-LAN.
        """
        mac = self.mac_address.replace(":", "").replace("-", "")
        if len(mac) != 12:
            raise ValueError("MAC address non valido")
        mac_bytes = bytes.fromhex(mac)
        magic_packet = b'\xff' * 6 + mac_bytes * 16
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(magic_packet, ('<broadcast>', 9))

    # --- POWER OFF (OMV API) ---

    def power_off(self) -> bool:
        """
        Spegne il NAS tramite chiamata API OMV.
        """
        try:
            cookies = self._omv_login()
        except Exception as e:
            logger.error(f"Errore in fase di login OMV: {e}")
            return False

        try:
            self._omv_shutdown(cookies)
        except Exception as e:
            logger.error(f"Errore in fase di shutdown OMV: {e}")
            return False

        logger.info("OMV server spento con successo.")
        return True

    def _omv_login(self):
        """
        Effettua il login all'OMV e restituisce i cookies di sessione.
        """
        json_data = {
            'service': 'Session',
            'method': 'login',
            'params': {
                'username': self.omv_user,
                'password': self.omv_password,
            },
        }
        response = requests.post(f'http://{self.omv_host}/rpc.php', json=json_data)
        response.raise_for_status()
        return response.cookies

    def _omv_shutdown(self, cookies):
        """
        Invia il comando di shutdown all'OMV.
        """
        json_data = {
            'service': 'System',
            'method': 'shutdown',
            'params': {
                'delay': 0,
            },
        }
        response = requests.post(f'http://{self.omv_host}/rpc.php', cookies=cookies, json=json_data)
        response.raise_for_status()

    # --- PING NAS ---

    def is_nas_online(self, timeout: int = 1) -> bool:
        """
        Verifica se il NAS risponde al ping.
        """
        if not self.omv_host:
            logger.warning("IP NAS non configurato per il ping.")
            return False
        param = '-n' if platform.system().lower() == 'windows' else '-c'
        try:
            import subprocess
            result = subprocess.run(
                ['ping', param, '1', '-w', str(timeout), self.omv_host],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Ping fallito: {e}")
            return False

    # --- CHECK MOUNT ---

    def is_mount_healthy(self, test_file: str = "") -> bool:
        """
        Verifica se la cartella montata è accessibile.
        """
        if not self.mount_path:
            logger.warning("Mount path non configurato.")
            return False
        test_path = os.path.join(self.mount_path, test_file) if test_file else self.mount_path
        try:
            ok, msg = self.run_ssh_command(self.ssh_host, self.ssh_user, self.ssh_password, f"ls {test_path}")
            if not msg:
                logger.warning("Cartella montata vuota. SUSPECT!")
                return False
            if not ok:
                logger.warning(f"Mount check fallito: {msg}")
            return ok
        except Exception as e:
            logger.warning(f"Mount check fallito: {e}")
            return False

    # --- REMOUNT (via SSH) ---

    def run_ssh_command(self, host, user, password, command):
        """
        Esegue un comando remoto via SSH usando paramiko (autenticazione user/password).
        """
        logger.info(f"Eseguo comando SSH su {host}: {command}")
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(hostname=host, username=user, password=password, timeout=10)
            stdin, stdout, stderr = ssh.exec_command(command)
            output = stdout.read().decode()
            error = stderr.read().decode()
            exit_status = stdout.channel.recv_exit_status()
            if exit_status != 0:
                logger.error(f"Errore SSH ({exit_status}): {error.strip()}")
                return False, error.strip()
            logger.info(f"Comando SSH eseguito: {command}")
            return True, output.strip()
        except Exception as e:
            logger.error(f"SSH connection failed: {e}")
            return False, str(e)
        finally:
            ssh.close()

    def remount_share_via_ssh(self):
        """
        Smonta e rimonta la share tramite SSH.
        """
        if not (self.ssh_host and self.ssh_user and self.ssh_password):
            logger.warning("Parametri SSH non configurati.")
            return False
        # Smonta
        ok, out = self.run_ssh_command(self.ssh_host, self.ssh_user, self.ssh_password, f"sudo umount {self.mount_path}")
        if not ok:
            logger.warning(f"Umount fallito: {out}")
            if "not mounted" in out.lower():
                logger.info("La share non era montata. Procedo al remount.")
            else:
                return self.remount_share_via_ssh()  # Riprova
        # Monta
        ok, out = self.run_ssh_command(self.ssh_host, self.ssh_user, self.ssh_password, f"sudo mount -a")
        if ok:
            logger.info("Remount via SSH riuscito.")
            return True
        else:
            logger.error(f"Remount via SSH fallito: {out}")
            return False
        
    def get_nas_status(self):
        """Restituisce lo stato di online/offline e della mount share."""
        online = self.is_nas_online()
        if not online:
            return False, False
        
        mount_ok = self.is_mount_healthy()
        return online, mount_ok