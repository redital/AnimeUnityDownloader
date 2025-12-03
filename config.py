import os

flask_app_config = {
    "debug": os.environ.get("FLASK_DEBUG", True),
    "host": os.environ.get("FLASK_HOST", "0.0.0.0"),
    "port": os.environ.get("FLASK_PORT", 5000),
    "ssl_context":os.environ.get("SSL_CONTEXT", None),
}


template_folder = os.environ.get("TEMPLATE_FOLDER_PATH",'web_app/templates')
static_folder = os.environ.get("STATIC_FOLDER_PATH",'web_app/static')

nas_mac_address = os.environ.get("NAS_MAC_ADDRESS", "placeholder")
nas_host_name = os.environ.get("NAS_HOST_NAME", "placeholder")

omv_user = os.environ.get("OMV_USER", "placeholder")
omv_password = os.environ.get("OMV_PASSWORD", "placeholder")
mount_path = os.environ.get("MOUNT_PATH", "placeholder")

ssh_host = os.environ.get("SSH_HOST", "placeholder")
ssh_user = os.environ.get("SSH_USER", "placeholder")
ssh_password = os.environ.get("SSH_PASSWORD", "placeholder")

