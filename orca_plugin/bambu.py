"""Bambu LAN MQTT/implicit FTPS. No cloud login, insecure TLS, or automatic replay."""
import ftplib
import copy
import hashlib
import json
import re
import socket
import ssl
import threading
import time
import urllib.parse
import uuid
import zipfile

from .common import OrcaError
from .http_printers import secret
from .monitoring import merge_delta, number, percent


COMMAND_TIMEOUT = 15


class PrinterTLS(ssl.SSLContext):
    """Verify the printer certificate against its serial rather than its IP."""
    def __new__(cls, ca_file, serial):
        return super().__new__(cls, ssl.PROTOCOL_TLS_CLIENT)

    def __init__(self, ca_file, serial):
        self.serial = serial
        self.load_verify_locations(cafile=ca_file)

    def wrap_socket(self, sock, **kwargs):
        kwargs["server_hostname"] = self.serial
        return super().wrap_socket(sock, **kwargs)


class ImplicitFTPS(ftplib.FTP_TLS):
    def store_file(self, filename, source):
        self.voidcmd("TYPE I")
        with self.transfercmd("STOR " + filename) as data:
            while block := source.read(65536):
                data.sendall(block)
            # Send close_notify so TLS peers receive a clean end of data, but
            # bound the wait: P1S does not send a reciprocal shutdown reply.
            data.settimeout(2)
            try:
                data.unwrap().close()
            except (TimeoutError, ssl.SSLEOFError):
                pass
        # A missing shutdown reply is not upload success. Require the FTP
        # completion response and, at the caller, matching remote file size.
        return self.voidresp()

    def connect(self, host, port=990, timeout=30, source_address=None):
        self.host, self.port, self.timeout = host, port, timeout
        raw = socket.create_connection((host, port), timeout, source_address)
        try:
            self.sock = self.context.wrap_socket(raw, server_hostname=host)
        except Exception:
            raw.close()
            raise
        self.af = self.sock.family
        self.file = self.sock.makefile("r", encoding=self.encoding)
        self.welcome = self.getresp()
        return self.welcome

    def ntransfercmd(self, cmd, rest=None):
        conn, size = ftplib.FTP.ntransfercmd(self, cmd, rest)
        try:
            if self._prot_p:
                conn = self.context.wrap_socket(conn, server_hostname=self.host, session=self.sock.session)
        except Exception:
            conn.close()
            raise
        return conn, size


class BambuLAN:
    def __init__(self, http):
        self.config = http.config
        self.options = self.config["options"]
        self.host = urllib.parse.urlsplit(self.config["url"]).hostname
        self.serial = self.options["serial"]
        self.client = None
        self.connected = threading.Event()
        self.subscribed = threading.Event()
        self.changed = threading.Condition()
        self.lock = threading.Lock()
        self.telemetry, self.replies = {}, {}
        self.last_seen = 0
        self.failure = None

    def tls(self):
        return PrinterTLS(self.options["ca_file"], self.serial)

    def connect(self):
        if self.client is not None:
            if not self.client.is_connected():
                raise OrcaError("Bambu MQTT disconnected. Restart the agent to reconnect; pending commands are never replayed.")
            return
        try:
            import paho.mqtt.client as mqtt
        except ImportError as exc:
            raise OrcaError("Bambu LAN requires paho-mqtt >=2,<3 in the Hermes Python environment. See connection setup.") from exc
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="hermes-orca-" + uuid.uuid4().hex[:12], reconnect_on_failure=False)
        client.connect_timeout = 15
        client.username_pw_set("bblp", secret(self.options, "access_code_env"))
        client.tls_set_context(self.tls())
        def on_connect(c, userdata, flags, reason, properties):
            if reason.is_failure:
                self.failure = "Bambu rejected MQTT authentication. Check access code and LAN/developer mode."
            else:
                c.subscribe(f"device/{self.serial}/report", qos=0)
            self.connected.set()
        def on_subscribe(c, userdata, mid, codes, properties):
            if any(code.is_failure for code in codes):
                self.failure = "Bambu refused the telemetry subscription."
            self.subscribed.set()
        def on_message(c, userdata, message):
            if message.retain or len(message.payload) > 2 * 1024 * 1024:
                return
            try:
                data = json.loads(message.payload).get("print", {})
                if not isinstance(data, dict):
                    return
                with self.changed:
                    if data.get("command") == "push_status":
                        merge_delta(self.telemetry, data)
                        self.last_seen = time.monotonic()
                    elif "sequence_id" in data:
                        self.replies[str(data["sequence_id"])] = data
                        if len(self.replies) > 100:
                            self.replies.pop(next(iter(self.replies)))
                    self.changed.notify_all()
            except (ValueError, AttributeError):
                pass
        client.on_connect, client.on_subscribe, client.on_message = on_connect, on_subscribe, on_message
        self.client = client
        try:
            client.connect(self.host, self.options.get("mqtt_port", 8883), keepalive=30)
            client.loop_start()
            if not self.connected.wait(15) or self.failure or not self.subscribed.wait(15):
                raise OrcaError(self.failure or "Bambu connection/subscription timed out.")
            # P1 printers send deltas. Request one full snapshot per connection, not per poll.
            self.publish({"pushing": {"command": "pushall", "sequence_id": "0", "version": 1, "push_target": 1}})
        except Exception as exc:
            client.disconnect()
            client.loop_stop()
            if isinstance(exc, OrcaError):
                raise
            if isinstance(exc, ssl.SSLCertVerificationError):
                raise OrcaError("Printer TLS certificate verification failed. Check the trusted CA file and exact serial number; verification has not been disabled.") from exc
            raise OrcaError("Cannot connect to Bambu LAN MQTT. Check printer IP, local network access and LAN/developer mode.") from exc

    def publish(self, payload):
        message = self.client.publish(f"device/{self.serial}/request", json.dumps(payload), qos=0, retain=False)
        message.wait_for_publish(timeout=10)
        if not message.is_published():
            raise OrcaError("Bambu command delivery unknown. Check status; do not retry.")

    def status(self):
        self.connect()
        deadline = time.monotonic() + 15
        with self.changed:
            while (not self.telemetry.get("gcode_state") or time.monotonic() - self.last_seen > 15) and time.monotonic() < deadline:
                self.changed.wait(max(0, deadline - time.monotonic()))
            data = copy.deepcopy(self.telemetry)
            fresh = time.monotonic() - self.last_seen <= 15 and self.client.is_connected()
        state = data.get("gcode_state", "UNKNOWN")
        trays = []
        for ams in data.get("ams", {}).get("ams", []):
            for tray in ams.get("tray", []):
                trays.append({"ams_id": ams.get("id"), "tray_id": tray.get("id"), "material": tray.get("tray_type"),
                              "color": tray.get("tray_color"), "remaining_percent": percent(tray.get("remain"))})
        return {"state": state if fresh else "UNKNOWN", "ready_to_start": fresh and state in {"IDLE", "FINISH"} and data.get("print_error", 0) in (0, "0") and data.get("sdcard") is True,
                "progress": number(data.get("mc_percent")), "progress_percent": percent(data.get("mc_percent")),
                "filename": data.get("gcode_file") or data.get("subtask_name"), "remaining_minutes": number(data.get("mc_remaining_time")),
                "remaining_seconds": number(data.get("mc_remaining_time"), 60),
                "nozzle_diameter": data.get("nozzle_diameter"), "telemetry_fresh": fresh,
                "telemetry_age_seconds": round(time.monotonic() - self.last_seen, 2),
                "layer": data.get("layer_num"), "total_layers": data.get("total_layer_num"),
                "temperatures": {"nozzle": {"actual": number(data.get("nozzle_temper")), "target": number(data.get("nozzle_target_temper"))},
                                 "bed": {"actual": number(data.get("bed_temper")), "target": number(data.get("bed_target_temper"))}},
                "error_code": data.get("print_error"), "hms": data.get("hms", []),
                # Orca's shipped HMS catalog labels 0300400C as cancellation.
                # Preserve the raw FAILED state/code for troubleshooting.
                "cancelled": fresh and state == "FAILED" and number(data.get("print_error")) == 0x0300400C,
                "stage_code": data.get("stg_cur"), "ams_trays": trays,
                "note": "Temperatures and material entries are last-reported telemetry; freshness does not certify physical readiness."}

    def validate_job(self, path, job):
        plate_path = f'Metadata/plate_{job["plate"]}.gcode'
        if path.stat().st_size > 256 * 1024 * 1024:
            raise OrcaError("Use native Orca upload for projects larger than 256 MB.")
        with zipfile.ZipFile(path) as archive:
            if plate_path not in archive.namelist():
                raise OrcaError("Bambu upload requires a sliced 3MF containing the selected plate's G-code.")
            if archive.getinfo(plate_path).file_size > 512 * 1024 * 1024:
                raise OrcaError("Plate G-code exceeds the inspection limit.")
            used_tools = set()
            with archive.open(plate_path) as gcode:
                for line in gcode:
                    match = re.match(rb"^T(\d+)\b", line.strip())
                    if match and int(match[1]) < 64:
                        used_tools.add(int(match[1]))
            if self.options.get("use_ams"):
                mapping = self.options["ams_mapping"]
                if any(tool >= len(mapping) or mapping[tool] < 0 for tool in (used_tools or {0})):
                    raise OrcaError("AMS mapping does not cover every tool used by this plate.")
            elif len(used_tools) > 1:
                raise OrcaError("Multiple filament tools require explicit AMS mapping or native Orca submission.")
        return {"plate_path": plate_path, "md5": hashlib.md5(path.read_bytes(), usedforsecurity=False).hexdigest()}

    def upload(self, path, filename):
        if path.stat().st_size > 256 * 1024 * 1024:
            raise OrcaError("Use native Orca upload for projects larger than 256 MB.")
        try:
            with ImplicitFTPS(context=self.tls()) as ftp:
                ftp.connect(self.host, self.options.get("ftps_port", 990))
                ftp.login("bblp", secret(self.options, "access_code_env"))
                ftp.prot_p()
                with path.open("rb") as source:
                    ftp.store_file(filename, source)
                ftp.voidcmd("TYPE I")
                if ftp.size(filename) != path.stat().st_size:
                    raise OrcaError("Bambu upload size could not be verified. No start receipt created.")
        except (OSError, ftplib.Error, EOFError) as exc:
            raise OrcaError("Bambu FTPS upload failed; check LAN access, certificate and SD card. No print started by this operation.") from exc
        return filename

    def command(self, command, **fields):
        with self.lock:
            self.connect()
            sequence = str(time.time_ns() // 1000)
            self.publish({"print": {"sequence_id": sequence, "command": command, **fields}})
            deadline = time.monotonic() + COMMAND_TIMEOUT
            with self.changed:
                while sequence not in self.replies and time.monotonic() < deadline:
                    self.changed.wait(max(0, deadline - time.monotonic()))
                reply = self.replies.pop(sequence, None)
            if not reply:
                raise OrcaError("Bambu command outcome unknown: no matching printer acknowledgment. Check status; do not retry.")
            if str(reply.get("result", "")).lower() != "success":
                raise OrcaError("Bambu did not accept the command. Check printer state and firmware authorization.")
            return reply

    def start(self, remote, details):
        return self.command("project_file", param=details["plate_path"], project_id="0", profile_id="0", task_id="0", subtask_id="0",
                            subtask_name=remote, url="ftp:///" + remote, md5=details["md5"], bed_type="auto",
                            use_ams=self.options.get("use_ams", False), ams_mapping=self.options.get("ams_mapping", []),
                            bed_levelling=self.options.get("bed_levelling", True), flow_cali=self.options.get("flow_cali", False),
                            vibration_cali=self.options.get("vibration_cali", False), timelapse=self.options.get("timelapse", False), layer_inspect=False)

    def control(self, action):
        return self.command({"pause": "pause", "resume": "resume", "cancel": "stop"}[action])
