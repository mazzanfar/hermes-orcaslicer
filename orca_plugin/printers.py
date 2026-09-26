"""Protocol adapters, independent of printer make/model.

Only configured endpoints are contacted. Upload never starts a print. Start
attempts are durable and never retried automatically after an uncertain reply.
"""
from __future__ import annotations

import json
import os
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from .common import OrcaError, identifier, read_json, sha256, write_json


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise OrcaError("Printer redirected the request. Configure the final endpoint explicitly; credentials were not forwarded.")


class HTTP:
    def __init__(self, config):
        self.config = config
        parsed = urllib.parse.urlsplit(config["url"])
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise OrcaError("Use an http(s) printer base URL without credentials, query, or fragment.")
        self.base = config["url"].rstrip("/")
        self.opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context()))

    def request(self, method, path, data=None, content_type=None):
        headers = {"Accept": "application/json"}
        env = self.config.get("api_key_env")
        if env:
            secret = os.environ.get(env)
            if not secret:
                raise OrcaError(f"Set the API key in environment variable {env}.")
            headers["X-Api-Key"] = secret
        if isinstance(data, dict):
            data = json.dumps(data).encode()
            content_type = "application/json"
        if content_type:
            headers["Content-Type"] = content_type
        request = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=30) as response:
                raw = response.read(8 * 1024 * 1024 + 1)
                if len(raw) > 8 * 1024 * 1024:
                    raise OrcaError("Printer response exceeded the size limit.")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            raise OrcaError(f"Printer returned HTTP {code}. Check connection, permissions and printer state.") from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise OrcaError("Printer request failed or timed out. Its outcome may be unknown; check status before any further action.") from exc
        except ValueError as exc:
            raise OrcaError("Printer returned invalid JSON.") from exc

    def upload(self, endpoint, path, filename, fields):
        if path.stat().st_size > 256 * 1024 * 1024:
            raise OrcaError("Remote uploads are limited to 256 MB; use file export for larger jobs.")
        boundary = "hermesorca" + uuid.uuid4().hex
        chunks = []
        for key, value in fields.items():
            chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
        chunks += [f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode(),
                   path.read_bytes(), f"\r\n--{boundary}--\r\n".encode()]
        return self.request("POST", endpoint, b"".join(chunks), f"multipart/form-data; boundary={boundary}")


class Moonraker:
    def __init__(self, http):
        self.http = http

    def status(self):
        result = self.http.request("GET", "/printer/objects/query?print_stats&webhooks&virtual_sdcard")["result"]["status"]
        state = result.get("print_stats", {}).get("state", "unknown")
        ready = result.get("webhooks", {}).get("state") == "ready"
        return {"state": state, "ready_to_start": ready and state in {"standby", "complete", "cancelled"},
                "filename": result.get("print_stats", {}).get("filename"),
                "progress": result.get("virtual_sdcard", {}).get("progress")}

    def upload(self, path, filename):
        result = self.http.upload("/server/files/upload", path, filename, {"root": "gcodes"})
        if result.get("print_started"):
            raise OrcaError("Printer unexpectedly started during upload; inspect it immediately.")
        return result["result"]["item"]["path"] if "result" in result else result["item"]["path"]

    def start(self, remote):
        return self.http.request("POST", "/printer/print/start", {"filename": remote})

    def control(self, action):
        return self.http.request("POST", "/printer/print/" + action)


class OctoPrint:
    def __init__(self, http):
        self.http = http

    def status(self):
        printer = self.http.request("GET", "/api/printer")
        job = self.http.request("GET", "/api/job")
        flags = printer.get("state", {}).get("flags", {})
        busy = any(flags.get(k) for k in ("printing", "paused", "pausing", "cancelling", "error", "closedOrError"))
        return {"state": job.get("state", "unknown"), "ready_to_start": bool(flags.get("operational")) and not busy,
                "filename": job.get("job", {}).get("file", {}).get("name"), "progress": job.get("progress", {}).get("completion")}

    def upload(self, path, filename):
        result = self.http.upload("/api/files/local", path, filename, {"select": "false", "print": "false"})
        return result["files"]["local"]["path"]

    def start(self, remote):
        return self.http.request("POST", "/api/files/local/" + urllib.parse.quote(remote, safe="/"), {"command": "select", "print": True})

    def control(self, action):
        body = {"command": "cancel"} if action == "cancel" else {"command": "pause", "action": action}
        return self.http.request("POST", "/api/job", body)


ADAPTERS = {"moonraker": Moonraker, "octoprint": OctoPrint}


class Printers:
    def __init__(self, base, slicer, http_factory=HTTP):
        self.base = base
        self.slicer = slicer
        self.http_factory = http_factory

    def configure(self, name, kind, printer_profile, url=None, api_key_env=None):
        identifier(name)
        if kind not in {*ADAPTERS, "file"}:
            raise OrcaError("Connection must be file, moonraker, or octoprint. File export works with any Orca-supported printer.")
        if not isinstance(printer_profile, str) or not printer_profile.strip():
            raise OrcaError("Supply the exact Orca printer preset name, including nozzle size.")
        config = {"name": name, "kind": kind, "printer_profile": printer_profile}
        if kind != "file":
            if not url:
                raise OrcaError("A printer URL is required.")
            config["url"] = url
            HTTP(config)  # Validation only; no network I/O.
            if api_key_env:
                if not re.fullmatch(r"[A-Z_][A-Z0-9_]*", api_key_env):
                    raise OrcaError("Supply the environment variable NAME, not an API key.")
                config["api_key_env"] = api_key_env
        path = self.base / "printers" / f"{name}.json"
        if path.exists():
            raise OrcaError("Printer name already exists. Use a new name to keep existing job receipts valid.")
        write_json(path, config)
        return {"configured": name, "kind": kind, "printer_profile": printer_profile}

    def list(self):
        return [read_json(p) for p in sorted((self.base / "printers").glob("*.json"))]

    def config(self, name):
        path = self.base / "printers" / f"{identifier(name)}.json"
        config = read_json(path)
        return config

    def adapter(self, config):
        if config["kind"] == "file":
            raise OrcaError("This printer uses file handoff. Export the artifact and use its SD/USB/native upload workflow.")
        return ADAPTERS[config["kind"]](self.http_factory(config))

    def status(self, name):
        config = self.config(name)
        if config["kind"] == "file":
            return {"state": "manual_handoff", "capabilities": ["export"], "print_started": False}
        return self.adapter(config).status()

    def upload(self, name, job_id, artifact):
        config = self.config(name)
        path, job = self.slicer.artifact(job_id, artifact)
        if path.suffix.lower() != ".gcode":
            raise OrcaError("This connection accepts plain G-code only. Do not send Bambu/other 3MF containers through it.")
        if job["printer_profile"] != config["printer_profile"]:
            raise OrcaError("Job printer/nozzle preset does not match the configured destination.")
        adapter = self.adapter(config)
        if not adapter.status()["ready_to_start"]:
            raise OrcaError("Printer is busy, disconnected or not ready; upload was not attempted.")
        remote_name = f"hermes-{job_id}-{uuid.uuid4().hex[:8]}.gcode"
        remote = adapter.upload(path, remote_name)
        if not isinstance(remote, str) or not remote or any(c in remote for c in ("\r", "\n")) or ".." in remote.split("/"):
            raise OrcaError("Printer returned an invalid remote filename.")
        receipt_id = uuid.uuid4().hex
        receipt = {"id": receipt_id, "printer": name, "config": config, "job_id": job_id,
                   "artifact": artifact, "sha256": sha256(path), "remote": remote,
                   "uploaded_at": time.time(), "state": "uploaded"}
        write_json(self.base / "receipts" / f"{receipt_id}.json", receipt)
        return {"receipt_id": receipt_id, "remote": remote, "print_started": False,
                "next": "Review job and destination, confirm clear bed/material, then explicitly request start."}

    def start(self, receipt_id, confirmed=False):
        if confirmed is not True:
            raise OrcaError("Start requires explicit user intent for this job and confirmation of bed/material readiness.")
        receipt_path = self.base / "receipts" / f"{identifier(receipt_id)}.json"
        receipt = read_json(receipt_path)
        if time.time() - receipt["uploaded_at"] > 3600:
            raise OrcaError("Upload receipt expired after one hour. Re-upload to review a fresh job.")
        config = self.config(receipt["printer"])
        if config != receipt["config"]:
            raise OrcaError("Printer configuration changed since upload.")
        path, _ = self.slicer.artifact(receipt["job_id"], receipt["artifact"])
        if sha256(path) != receipt["sha256"]:
            raise OrcaError("Artifact changed since upload.")
        adapter = self.adapter(config)
        if not adapter.status()["ready_to_start"]:
            raise OrcaError("Printer is not ready; start was not attempted.")
        attempt = receipt_path.with_suffix(".attempt")
        try:
            with attempt.open("x") as f:
                f.write(str(time.time()))
        except FileExistsError as exc:
            raise OrcaError("Start was already attempted. Check printer status; this operation will not retry.") from exc
        receipt["state"] = "start_outcome_unknown"
        write_json(receipt_path, receipt)
        adapter.start(receipt["remote"])
        receipt["state"] = "start_accepted"
        write_json(receipt_path, receipt)
        return {"receipt_id": receipt_id, "state": "start_accepted", "note": "Command accepted; poll printer status to verify actual printing."}

    def control(self, name, action, confirmed=False):
        if action not in {"pause", "resume", "cancel"}:
            raise OrcaError("Action must be pause, resume or cancel.")
        if confirmed is not True:
            raise OrcaError("Printer control requires explicit user intent.")
        self.adapter(self.config(name)).control(action)
        return {"action": action, "state": "command_accepted", "next": "Poll status to verify."}
