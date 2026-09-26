"""Connection options are explicit, bounded, and contain secret variable names only."""
import re
from pathlib import Path
from .common import OrcaError


def validate_options(kind, options):
    allowed = {
        "file": set(), "moonraker": set(), "octoprint": set(),
        "prusalink": {"storage", "username", "password_env"},
        "duet": {"password_env"},
        "flashforge_http": {"serial", "access_code_env", "bed_levelling"},
        "bambu_lan": {"serial", "access_code_env", "ca_file", "mqtt_port", "ftps_port", "use_ams", "ams_mapping", "bed_levelling", "flow_cali", "vibration_cali", "timelapse"},
    }
    if not isinstance(options, dict) or set(options) - allowed[kind]:
        raise OrcaError("Unsupported connection options for this protocol.")
    for key, value in options.items():
        if key.endswith("_env") and (not isinstance(value, str) or not re.fullmatch(r"[A-Z_][A-Z0-9_]*", value)):
            raise OrcaError("Credentials must be supplied by environment variable NAME.")
        if key.endswith("_port") and (type(value) is not int or not 1 <= value <= 65535):
            raise OrcaError("Port must be an integer from 1 to 65535.")
        if key in {"use_ams", "bed_levelling", "flow_cali", "vibration_cali", "timelapse"} and type(value) is not bool:
            raise OrcaError(f"{key} must be a boolean.")
    if kind == "prusalink":
        if options.get("storage", "usb") not in {"usb", "local", "sdcard"}:
            raise OrcaError("PrusaLink storage must be usb, local or sdcard.")
        if bool(options.get("username")) != bool(options.get("password_env")):
            raise OrcaError("Digest authentication requires both username and password_env.")
    if kind in {"bambu_lan", "flashforge_http"}:
        if not options.get("access_code_env"):
            raise OrcaError("Supply access_code_env for the printer access code.")
        if not re.fullmatch(r"[A-Za-z0-9_-]{5,64}", str(options.get("serial", ""))):
            raise OrcaError("Supply a valid printer serial number.")
    if kind == "bambu_lan":
        if not options.get("access_code_env") or not options.get("ca_file"):
            raise OrcaError("Bambu LAN requires access_code_env and a trusted CA/certificate file (ca_file).")
        path = Path(options["ca_file"]).expanduser().resolve()
        if not path.is_file():
            raise OrcaError("The trusted Bambu CA/certificate file does not exist.")
        options = dict(options, ca_file=str(path))
        mapping = options.get("ams_mapping", [])
        if not isinstance(mapping, list) or any(type(n) is not int or n < -1 or n > 255 for n in mapping):
            raise OrcaError("AMS mapping must be a list of tray indices; -1 denotes an unused filament.")
        if options.get("use_ams") and not mapping:
            raise OrcaError("AMS use requires an explicit reviewed filament-to-tray mapping.")
    return options


def capabilities():
    return {"slicing": "Installed Orca printer profiles, including user profiles",
            "connections": {
                "file": {"artifacts": [".gcode", ".3mf"], "operations": ["export"]},
                **{kind: {"artifacts": [".gcode"], "operations": ["status", "upload", "start", "pause", "resume", "cancel"], "hardware_validated": False}
                   for kind in ("octoprint", "moonraker", "prusalink", "duet", "flashforge_http")},
                "bambu_lan": {"artifacts": [".3mf"], "operations": ["status", "upload", "start", "pause", "resume", "cancel"],
                              "requires": "LAN MQTT/FTPS access, paho-mqtt 2.x, trusted printer CA/certificate, serial and access code", "hardware_validated": False}},
            "native_review": "Orca GUI provides full arrangement, per-object editing and toolpath preview; save edits and prepare a new job.",
            "unsupported_connections": ["Bambu cloud", "Flashforge legacy TCP/material stations", "Prusa Connect", "Duet Software Framework", "other vendor/cloud protocols"]}
