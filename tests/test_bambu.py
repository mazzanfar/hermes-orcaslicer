"""One Bambu tool-to-TLS workflow; actual MQTT/FTPS sockets, simulated printer."""
import importlib.util
import json
import os
import shutil
import socket
import socketserver
import ssl
import struct
import subprocess
import threading
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from orca_plugin.common import sha256, write_json
from tests.test_workflow import Base, GCODE
from tests.tools_harness import Tools


def packet(kind, payload):
    length, encoded = len(payload), bytearray()
    while True:
        byte = length % 128
        length //= 128
        encoded.append(byte | (128 if length else 0))
        if not length:
            return bytes([kind]) + encoded + payload


def exact(sock, size):
    result = b""
    while len(result) < size:
        chunk = sock.recv(size - len(result))
        if not chunk:
            raise EOFError
        result += chunk
    return result


class TLSHandler(socketserver.BaseRequestHandler):
    def handle(self):
        try:
            with self.server.tls.wrap_socket(self.request, server_side=True) as sock:
                sock.settimeout(20)
                self.exchange(sock)
        except (EOFError, OSError):
            pass


class MQTT(TLSHandler):
    def exchange(self, sock):
        s = self.server.printer
        topic = b"device/TESTSERIAL/report"
        def report(body):
            payload = struct.pack("!H", len(topic)) + topic + json.dumps({"print": body}).encode()
            sock.sendall(packet(0x30, payload))
        def status():
            report({"command": "push_status", "gcode_state": s.state, "print_error": 0x0300400C if s.state == "FAILED" and not getattr(s, "clear_cancel_code", False) else 0, "sdcard": True,
                    "gcode_file": getattr(s, "filename", ""), "mc_percent": 100 if s.state == "FINISH" else 25,
                    "nozzle_temper": 215, "nozzle_target_temper": 220, "bed_temper": 55, "bed_target_temper": 55,
                    "layer_num": 5, "total_layer_num": 20,
                    "ams": {"ams": [{"id": "0", "tray": [{"id": "0", "tray_type": "PLA"}]}]}})
            report({"command": "push_status", "ams": {"tray_now": "0"}})
        while True:
            kind = exact(sock, 1)[0] >> 4
            length = shift = 0
            while True:
                byte = exact(sock, 1)[0]
                length += (byte & 127) << shift
                shift += 7
                if byte < 128:
                    break
            data = exact(sock, length)
            if kind == 1:
                sock.sendall(b"\x20\x02\x00\x00" if b"test-access-code" in data else b"\x20\x02\x00\x05")
            elif kind == 8:
                sock.sendall(packet(0x90, data[:2] + b"\x00"))
            elif kind == 3:
                topic_length = struct.unpack("!H", data[:2])[0]
                request = json.loads(data[2 + topic_length:])
                if "pushing" in request:
                    status()
                    continue
                body = request["print"]
                command = body["command"]
                if command == "project_file":
                    s.starts += 1
                    s.start_body = body
                    s.filename = body["subtask_name"]
                    s.state = "RUNNING"
                else:
                    s.state = {"pause": "PAUSE", "resume": "RUNNING", "stop": "FAILED"}[command]
                status()
                if not (s.lose_reply and command == "project_file"):
                    report({"command": command, "sequence_id": body["sequence_id"], "result": "success"})
            elif kind == 12:
                sock.sendall(b"\xd0\x00")
                status()
            elif kind == 14:
                return


class FTPS(TLSHandler):
    def exchange(self, sock):
        s = self.server.printer
        passive = None
        def reply(text):
            sock.sendall((text + "\r\n").encode())
        reply("220 Test printer")
        with sock.makefile("rb") as stream:
            for raw in stream:
                command, _, value = raw.decode().strip().partition(" ")
                if command == "USER":
                    reply("331 Password required")
                elif command == "PASS":
                    reply("230 Logged in" if value == "test-access-code" else "530 Denied")
                elif command in {"PBSZ", "PROT", "TYPE"}:
                    reply("200 OK")
                elif command == "PASV":
                    passive = socket.create_server(("127.0.0.1", 0))
                    port = passive.getsockname()[1]
                    reply(f"227 Entering Passive Mode (127,0,0,1,{port // 256},{port % 256})")
                elif command == "STOR":
                    reply("150 Data connection")
                    raw_data, _ = passive.accept()
                    passive.close()
                    with self.server.tls.wrap_socket(raw_data, server_side=True) as data:
                        content = b""
                        while chunk := data.recv(65536):
                            content += chunk
                        # Match P1S: wait for data-socket EOF, without a
                        # reciprocal TLS close_notify shutdown exchange.
                    s.uploaded[value] = content
                    reply("226 Stored")
                elif command == "SIZE":
                    reply("213 " + str(len(s.uploaded[value])))
                elif command == "QUIT":
                    reply("221 Goodbye")
                    return
                else:
                    reply("500 Unsupported test command")


class Camera(TLSHandler):
    def exchange(self, sock):
        header = struct.unpack("<IIII32s32s", exact(sock, 80))
        if header[:4] != (0x40, 0x3000, 0, 0) or header[4].rstrip(b"\0") != b"bblp" or header[5].rstrip(b"\0") != b"test-access-code":
            return
        data = (Path(__file__).parent / "fixtures/camera.jpg").read_bytes()
        if self.server.printer.camera_failure:
            sock.sendall(struct.pack("<IIII", 9 * 1024 * 1024, 0, 1, 0))
            return
        packet = struct.pack("<IIII", len(data), 0, 1, 0) + data
        for i in range(0, len(packet), 7):
            sock.sendall(packet[i:i + 7])


@unittest.skipUnless(importlib.util.find_spec("paho") and shutil.which("openssl"), "Bambu TLS workflow requires the bambu extra and openssl")
class BambuWorkflow(Base):
    def test_upload_print_control_and_unknown_reply_across_restart(self):
        cert, key = self.base / "cert.pem", self.base / "test.key"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(key), "-out", str(cert),
                        "-subj", "/CN=TESTSERIAL", "-addext", "subjectAltName=DNS:TESTSERIAL", "-days", "1"], check=True, capture_output=True)
        self.state, self.starts, self.lose_reply, self.uploaded = "IDLE", 0, False, {}
        self.camera_failure = False
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.load_cert_chain(cert, key)
        ports = []
        for handler in (MQTT, FTPS, Camera):
            server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
            server.daemon_threads = True
            server.tls, server.printer = tls, self
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(server.server_close)
            self.addCleanup(server.shutdown)
            ports.append(server.server_address[1])
        directory = self.base / "jobs/job1"
        directory.mkdir(parents=True)
        model = directory / "sliced.3mf"
        with zipfile.ZipFile(model, "w") as archive:
            archive.writestr("Metadata/plate_1.gcode", GCODE)
        write_json(directory / "job.json", {"id": "job1", "state": "sliced", "plate": 1, "printer_profile": "Bambu Lab P1S 0.4 nozzle",
                    "artifacts": [{"name": model.name, "path": str(model), "sha256": sha256(model)}]})
        with patch.dict(os.environ, {"ORCA_BAMBU_TEST_CODE": "test-access-code"}), patch("orca_plugin.bambu.COMMAND_TIMEOUT", 0.5):
            tools = Tools(self.base)
            tools.call("orca_printer_configure", name="p1s", kind="bambu_lan", url="https://127.0.0.1", printer_profile="Bambu Lab P1S 0.4 nozzle",
                       options={"serial": "TESTSERIAL", "access_code_env": "ORCA_BAMBU_TEST_CODE", "ca_file": str(cert), "mqtt_port": ports[0], "ftps_port": ports[1], "camera_protocol": "bambu_jpeg", "camera_port": ports[2]})
            self.assertTrue(tools.call("orca_printer_status", name="p1s")["ready_to_start"])
            snapshot = tools.call("orca_camera_snapshot", name="p1s")
            self.assertEqual(Path(snapshot["path"]).read_bytes(), (Path(__file__).parent / "fixtures/camera.jpg").read_bytes())
            self.assertFalse(snapshot["physical_readiness_verified"])
            tools.call("orca_printer_configure", name="wrong-camera-identity", kind="bambu_lan", url="https://127.0.0.1", printer_profile="Bambu Lab P1S 0.4 nozzle",
                       options={"serial": "WRONGSERIAL", "access_code_env": "ORCA_BAMBU_TEST_CODE", "ca_file": str(cert), "camera_protocol": "bambu_jpeg", "camera_port": ports[2]})
            self.assertIn("verification remains enabled", tools.reject("orca_camera_snapshot", name="wrong-camera-identity"))
            self.camera_failure = True
            self.assertIn("size limit", tools.reject("orca_camera_snapshot", name="p1s"))
            self.camera_failure = False
            review = tools.call("orca_preflight", name="p1s", job_id="job1", artifact=model.name, expected_bed_type="Cool Plate")
            self.assertFalse(review["checks_passed"])
            self.assertFalse(review["physical_readiness_verified"])
            self.assertFalse(review["printer_contacted"])
            self.assertEqual(review["first_layer_bed_temperature"], "55")
            self.assertEqual(review["material_source"], "external_spool")
            self.assertIn("bed type", tools.reject("orca_upload", name="p1s", job_id="job1", artifact=model.name, expected_bed_type="Cool Plate"))
            self.assertEqual(self.uploaded, {})
            receipt = tools.call("orca_upload", name="p1s", job_id="job1", artifact=model.name, expected_bed_type="Textured PEI Plate")
            self.assertTrue(receipt["preflight"]["checks_passed"])
            self.assertEqual(self.uploaded[receipt["remote"]], model.read_bytes())
            self.assertEqual(self.starts, 0)
            tools.call("orca_start", receipt_id=receipt["receipt_id"], confirmed=True)
            observed = tools.call("orca_monitor", name="p1s", receipt_id=receipt["receipt_id"])
            self.assertEqual(observed["job_match"], "match")
            self.assertEqual(observed["job_outcome"], "printing")
            self.assertEqual(observed["status"]["temperatures"]["nozzle"]["actual"], 215)
            self.assertEqual(observed["status"]["ams_trays"][0]["material"], "PLA")
            self.assertEqual(self.start_body["param"], "Metadata/plate_1.gcode")
            self.assertFalse(self.start_body["use_ams"])
            for action, state in (("pause", "PAUSE"), ("resume", "RUNNING"), ("cancel", "FAILED")):
                tools.call("orca_printer_control", name="p1s", action=action, confirmed=True)
                self.assertEqual(tools.call("orca_printer_status", name="p1s")["state"], state)
            observed = tools.call("orca_monitor", name="p1s", receipt_id=receipt["receipt_id"])
            self.assertEqual(observed["job_outcome"], "cancelled")
            self.assertFalse(observed["status"]["requires_attention"])
            self.assertFalse(observed["status"]["ready_to_start"])
            self.clear_cancel_code = True
            observed = Tools(self.base).call("orca_monitor", name="p1s", receipt_id=receipt["receipt_id"])
            self.assertEqual(observed["status"]["error_code"], 0)
            self.assertEqual(observed["job_outcome"], "cancelled")
            saved_filename, self.filename = self.filename, "different-cancelled-job.3mf"
            observed = Tools(self.base).call("orca_monitor", name="p1s", receipt_id=receipt["receipt_id"])
            self.assertEqual(observed["status"]["phase"], "error")
            self.assertEqual(observed["job_outcome"], "unknown")
            self.filename = saved_filename
            self.state = "IDLE"
            tools = Tools(self.base)
            receipt = tools.call("orca_upload", name="p1s", job_id="job1", artifact=model.name)
            self.lose_reply = True
            self.assertIn("unknown", tools.reject("orca_start", receipt_id=receipt["receipt_id"], confirmed=True))
            self.state = "IDLE"
            restarted = Tools(self.base)
            self.assertIn("already attempted", restarted.reject("orca_start", receipt_id=receipt["receipt_id"], confirmed=True))
            self.assertEqual(self.starts, 2)
            self.state = "FINISH"
            observed = Tools(self.base).call("orca_monitor", name="p1s", receipt_id=receipt["receipt_id"])
            self.assertEqual(observed["job_outcome"], "completed")
            self.filename = "another-job.3mf"
            observed = Tools(self.base).call("orca_monitor", name="p1s", receipt_id=receipt["receipt_id"])
            self.assertEqual(observed["job_match"], "different_job")
            self.assertEqual(observed["job_outcome"], "unknown")
            tools.call("orca_printer_configure", name="ams", kind="bambu_lan", url="https://127.0.0.1", printer_profile="Bambu Lab P1S 0.4 nozzle",
                       options={"serial": "TESTSERIAL", "access_code_env": "ORCA_BAMBU_TEST_CODE", "ca_file": str(cert), "use_ams": True, "ams_mapping": [0]})
            review = tools.call("orca_preflight", name="ams", job_id="job1", artifact=model.name, expected_bed_type="Textured PEI Plate")
            self.assertEqual(review["material_source"], "AMS")
            self.assertEqual(review["ams_mapping"], [0])
