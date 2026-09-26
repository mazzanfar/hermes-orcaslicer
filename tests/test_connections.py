"""Tool-to-HTTP acceptance tests. The local server simulates, not certifies, hardware."""
import json
import os
import threading
import time
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from tests.test_workflow import Base
from tests.tools_harness import Tools


class PrinterServer(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.respond()

    def do_POST(self):
        self.respond()

    def respond(self):
        s = self.server
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        s.calls.append((self.command, self.path))
        code, result = 200, {}
        if self.headers.get("X-Api-Key") != "test-only-key":
            code, result = 401, {"error": "private-server-details"}
        elif s.failure == "redirect":
            self.send_response(302)
            self.send_header("Location", s.url + "/redirect-target")
            self.end_headers()
            return
        elif self.path.startswith("/printer/objects"):
            result = {"result": {"status": {"print_stats": {"state": s.state}, "webhooks": {"state": "ready"}}}}
        elif self.path == "/api/printer":
            result = {"state": {"flags": {"operational": True, "printing": s.state == "printing", "paused": s.state == "paused"}}}
        elif self.path == "/api/job" and self.command == "GET":
            result = {"state": s.state}
        elif self.path in {"/server/files/upload", "/api/files/local"}:
            message = BytesParser(policy=default).parsebytes(
                ("Content-Type: " + self.headers["Content-Type"] + "\r\n\r\n").encode() + raw)
            parts = {p.get_param("name", header="content-disposition"): p for p in message.iter_parts()}
            s.upload = {k: p.get_payload(decode=True) for k, p in parts.items()}
            filename = parts["file"].get_filename()
            result = {"item": {"path": filename}, "print_started": False} if s.kind == "moonraker" else {"files": {"local": {"path": filename}}}
        else:
            body = json.loads(raw) if raw else {}
            starting = self.path == "/printer/print/start" or self.path.startswith("/api/files/local/")
            if starting:
                s.starts += 1
                s.start_body = body
                s.state = "printing"
                if s.failure == "lost_reply":
                    self.close_connection = True
                    return
            else:
                action = self.path.rsplit("/", 1)[-1] if s.kind == "moonraker" else body.get("action", body.get("command"))
                s.state = {"pause": "paused", "resume": "printing", "cancel": "cancelled"}[action]
        payload = json.dumps(result).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class ConnectionWorkflows(Base):
    def setUp(self):
        super().setUp()
        _, self.gcode = self.sliced()
        self.tools = Tools(self.base)
        env = patch.dict(os.environ, {"ORCA_TEST_KEY": "test-only-key"})
        env.start()
        self.addCleanup(env.stop)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), PrinterServer)
        self.server.url = f"http://127.0.0.1:{self.server.server_port}"
        self.server.calls, self.server.starts = [], 0
        self.server.failure, self.server.state = None, "standby"
        worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        worker.start()
        def cleanup():
            self.server.shutdown()
            self.server.server_close()
            worker.join()
        self.addCleanup(cleanup)

    def configure(self, kind):
        self.server.kind = kind
        self.tools.call("orca_printer_configure", name=kind, kind=kind, printer_profile="Example 0.4 nozzle",
                        url=self.server.url, api_key_env="ORCA_TEST_KEY")

    def upload(self, kind):
        return self.tools.call("orca_upload", name=kind, job_id="job1", artifact="plate.gcode")

    def test_upload_start_and_control_for_each_protocol(self):
        for kind in ("moonraker", "octoprint"):
            with self.subTest(protocol=kind):
                self.server.state, self.server.starts = "standby", 0
                self.configure(kind)
                receipt = self.upload(kind)
                self.assertFalse(receipt["print_started"])
                self.assertEqual(self.server.starts, 0)
                self.assertEqual(self.server.upload["file"], self.gcode.read_bytes())
                if kind == "octoprint":
                    self.assertEqual(self.server.upload["print"], b"false")
                    self.assertEqual(self.server.upload["select"], b"false")
                else:
                    self.assertEqual(self.server.upload["root"], b"gcodes")
                    self.assertNotIn("print", self.server.upload)
                self.tools.reject("orca_start", receipt_id=receipt["receipt_id"], confirmed=False)
                self.assertEqual(self.server.starts, 0)
                result = self.tools.call("orca_start", receipt_id=receipt["receipt_id"], confirmed=True)
                self.assertEqual(result["state"], "start_accepted")
                expected = {"filename": receipt["remote"]} if kind == "moonraker" else {"command": "select", "print": True}
                self.assertEqual(self.server.start_body, expected)
                for action, state in (("pause", "paused"), ("resume", "printing"), ("cancel", "cancelled")):
                    self.tools.call("orca_printer_control", name=kind, action=action, confirmed=True)
                    self.assertEqual(self.tools.call("orca_printer_status", name=kind)["state"], state)
                self.tools.reject("orca_start", receipt_id=receipt["receipt_id"], confirmed=True)
                self.assertEqual(self.server.starts, 1)

    def test_lost_start_reply_is_not_retried_after_restart(self):
        for kind in ("moonraker", "octoprint"):
            with self.subTest(protocol=kind):
                self.server.state, self.server.starts = "standby", 0
                self.configure(kind)
                receipt = self.upload(kind)
                self.server.failure = "lost_reply"
                self.tools.reject("orca_start", receipt_id=receipt["receipt_id"], confirmed=True)
                self.tools = Tools(self.base)
                self.assertEqual(self.tools.call("orca_printer_status", name=kind)["state"], "printing")
                self.server.failure, self.server.state = None, "standby"
                self.assertIn("already attempted", self.tools.reject("orca_start", receipt_id=receipt["receipt_id"], confirmed=True))
                self.assertEqual(self.server.starts, 1)

    def test_connection_and_receipt_guards(self):
        self.configure("moonraker")
        with patch.dict(os.environ, {"ORCA_TEST_KEY": "wrong"}):
            error = self.tools.reject("orca_printer_status", name="moonraker")
            self.assertIn("401", error)
            self.assertNotIn("private-server-details", error)
        self.server.failure = "redirect"
        self.assertIn("redirected", self.tools.reject("orca_printer_status", name="moonraker"))
        self.assertFalse(any(path == "/redirect-target" for _, path in self.server.calls))
        self.server.failure, self.server.state = None, "printing"
        self.tools.reject("orca_upload", name="moonraker", job_id="job1", artifact="plate.gcode")
        self.assertFalse(hasattr(self.server, "upload"))
        self.server.state = "standby"
        self.tools.call("orca_printer_configure", name="wrong-nozzle", kind="moonraker",
                        printer_profile="Example 0.6 nozzle", url=self.server.url)
        before = len(self.server.calls)
        self.assertIn("does not match", self.tools.reject("orca_upload", name="wrong-nozzle", job_id="job1", artifact="plate.gcode"))
        self.assertEqual(len(self.server.calls), before)
        receipt = self.upload("moonraker")
        with patch("orca_plugin.printers.time.time", return_value=time.time() + 4000):
            self.assertIn("expired", self.tools.reject("orca_start", receipt_id=receipt["receipt_id"], confirmed=True))
        self.gcode.write_text("changed after review")
        self.assertIn("changed", self.tools.reject("orca_start", receipt_id=receipt["receipt_id"], confirmed=True))
        self.assertEqual(self.server.starts, 0)
