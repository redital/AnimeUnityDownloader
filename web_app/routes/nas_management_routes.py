from flask import jsonify, Blueprint
from web_app.nas_power_manager import (
    get_nas_status,
    nas_power_on,
    nas_power_off,
    nas_remount,
)


nas_management_routes = Blueprint('nas_management', __name__)

@nas_management_routes.route('/nas/status', methods=['GET'])
def nas_status_route():
    result, status_code = get_nas_status()
    return jsonify(result), status_code


@nas_management_routes.route('/nas/power/on', methods=['POST'])
def nas_power_on_route():
    result, status_code = nas_power_on(False, False)
    return jsonify(result), status_code


@nas_management_routes.route('/nas/power/off', methods=['POST'])
def nas_power_off_route():
    result, status_code = nas_power_off()
    return jsonify(result), status_code


@nas_management_routes.route('/nas/remount', methods=['POST'])
def nas_remount_route():
    result, status_code = nas_remount()
    return jsonify(result), status_code
