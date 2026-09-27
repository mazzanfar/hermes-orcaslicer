"""Protocol adapters, independent of printer make/model.

Only configured endpoints are contacted. Upload never starts a print. Start
attempts are durable and never retried automatically after an uncertain reply.
"""
from __future__ import annotations

import json
import http.client
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from .common import OrcaError, credential_env_name, identifier, read_json, sha256, write_json
from .monitoring import number, percent, phase


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

    def request(self, method, path, data=None, content_type=None, headers=None):
        headers = {"Accept": "application/json", **(headers or {})}
        env = self.config.get("api_key_env")
        if env:
            secret = os.environ.get(env)
            if not secret:
                raise OrcaError(f"Set the API key in environment variable {env}.")
            headers["X-Api-Key"] = secret
        if isinstance(data, dict):
            data = json.dumps(data).encode()
            content_type = "application/json"
        options = self.config.get("options", {})
        if options.get("username") and options.get("password_env"):
            password = os.environ.get(options["password_env"])
            if not password:
                raise OrcaError("Set the configured password environment variable.")
            manager = urllib.request.HTTPPasswordMgrWithDefaultRealm()
            manager.add_password(None, self.base, options["username"], password)
            self.opener.add_handler(urllib.request.HTTPDigestAuthHandler(manager))
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
        except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as exc:
            raise OrcaError("Printer request failed or timed out. Its outcome may be unknown; check status before any further action.") from exc
        except ValueError as exc:
            raise OrcaError("Printer returned invalid JSON.") from exc

    def upload(self, endpoint, path, filename, fields, headers=None, field_name="file"):
        if path.stat().st_size > 256 * 1024 * 1024:
            raise OrcaError("Remote uploads are limited to 256 MB; use file export for larger jobs.")
        boundary = "hermesorca" + uuid.uuid4().hex
        chunks = []
        for key, value in fields.items():
            chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
        chunks += [f'--{boundary}\r\nContent-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode(),
                   path.read_bytes(), f"\r\n--{boundary}--\r\n".encode()]
        return self.request("POST", endpoint, b"".join(chunks), f"multipart/form-data; boundary={boundary}", headers=headers)


class Moonraker:
    def __init__(self, http):
        self.http = http

    def status(self):
        result = self.http.request("GET", "/printer/objects/query?print_stats&webhooks&virtual_sdcard&extruder&heater_bed")["result"]["status"]
        state = result.get("print_stats", {}).get("state", "unknown")
        ready = result.get("webhooks", {}).get("state") == "ready"
        return {"state": state, "ready_to_start": ready and state in {"standby", "complete", "cancelled"},
                "filename": result.get("print_stats", {}).get("filename"),
                "progress": result.get("virtual_sdcard", {}).get("progress"),
                "progress_percent": percent(result.get("virtual_sdcard", {}).get("progress"), 100),
                "elapsed_seconds": number(result.get("print_stats", {}).get("print_duration")),
                "message": result.get("print_stats", {}).get("message"),
                "layer": result.get("print_stats", {}).get("info", {}).get("current_layer"),
                "total_layers": result.get("print_stats", {}).get("info", {}).get("total_layer"),
                "temperatures": {label: {"actual": number(result.get(key, {}).get("temperature")), "target": number(result.get(key, {}).get("target"))}
                                 for label, key in (("nozzle", "extruder"), ("bed", "heater_bed"))}}

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
                "filename": job.get("job", {}).get("file", {}).get("name"), "progress": job.get("progress", {}).get("completion"),
                "progress_percent": percent(job.get("progress", {}).get("completion")),
                "elapsed_seconds": number(job.get("progress", {}).get("printTime")),
                "remaining_seconds": number(job.get("progress", {}).get("printTimeLeft")),
                "temperatures": {k: {"actual": number(v.get("actual")), "target": number(v.get("target"))}
                                 for k, v in printer.get("temperature", {}).items() if isinstance(v, dict)},
                "error": bool(flags.get("error") or flags.get("closedOrError"))}

    def upload(self, path, filename):
        result = self.http.upload("/api/files/local", path, filename, {"select": "false", "print": "false"})
        return result["files"]["local"]["path"]

    def start(self, remote):
        return self.http.request("POST", "/api/files/local/" + urllib.parse.quote(remote, safe="/"), {"command": "select", "print": True})

    def control(self, action):
        body = {"command": "cancel"} if action == "cancel" else {"command": "pause", "action": action}
        return self.http.request("POST", "/api/job", body)


from .http_printers import PrusaLink, Duet, Flashforge
from .bambu import BambuLAN

ADAPTERS = {"moonraker": Moonraker, "octoprint": OctoPrint, "prusalink": PrusaLink, "duet": Duet, "bambu_lan": BambuLAN, "flashforge_http": Flashforge}


class Printers:
    def __init__(self, base, slicer, http_factory=HTTP):
        self.base = base
        self.slicer = slicer
        self.http_factory = http_factory
        self._bambu = {}

    def configure(self, name, kind, printer_profile, url=None, api_key_env=None, options=None):
        identifier(name)
        if kind not in {*ADAPTERS, "file"}:
            raise OrcaError("Unknown connection protocol. Use orca_capabilities for supported protocols.")
        if not isinstance(printer_profile, str) or not printer_profile.strip():
            raise OrcaError("Supply the exact Orca printer preset name, including nozzle size.")
        config = {"name": name, "kind": kind, "printer_profile": printer_profile}
        if kind != "file":
            if not url:
                raise OrcaError("A printer URL is required.")
            config["url"] = url
            HTTP(config)  # Validation only; no network I/O.
            if api_key_env:
                config["api_key_env"] = credential_env_name(api_key_env)
        from .connections import require_encrypted_credentials, validate_options
        config["options"] = validate_options(kind, options or {})
        if kind != "file":
            require_encrypted_credentials(url, config["options"], api_key_env)
        if kind == "bambu_lan":
            endpoint = urllib.parse.urlsplit(url)
            if endpoint.scheme != "https" or endpoint.path not in ("", "/") or endpoint.port:
                raise OrcaError("Use https://PRINTER_HOST for Bambu LAN; set optional mqtt_port/ftps_port in options.")
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
        if config["kind"] == "bambu_lan":
            key = json.dumps(config, sort_keys=True)
            if key not in self._bambu:
                self._bambu[key] = BambuLAN(self.http_factory(config))
            return self._bambu[key]
        return ADAPTERS[config["kind"]](self.http_factory(config))

    def status(self, name):
        config = self.config(name)
        if config["kind"] == "file":
            return {"state": "manual_handoff", "phase": "manual_handoff", "ready_to_start": False,
                    "observed_at": time.time(), "capabilities": ["export"], "print_started": False}
        result = self.adapter(config).status()
        # Some Bambu firmware clears its cancellation code but retains FAILED.
        # Only recover cancellation from our accepted stop of this exact job;
        # never suppress a current non-cancellation fault or a different job.
        control_path = self.base / "controls" / f"{identifier(name)}.json"
        if config["kind"] == "bambu_lan" and result.get("state") == "FAILED" and result.get("error_code") in (None, 0, "0") and not result.get("hms") and control_path.exists():
            previous = read_json(control_path)
            if (previous.get("action") == "cancel" and previous.get("accepted") and previous.get("config") == config
                    and previous.get("before") in {"RUNNING", "PAUSE"} and previous.get("filename")
                    and previous["filename"] == result.get("filename") and result.get("telemetry_fresh")
                    and 0 <= time.time() - previous["issued_at"] <= 3600):
                result["cancelled"] = True
                result["cancellation_evidence"] = "Matching stopped job after an accepted cancel command; firmware cleared its code."
        result["observed_at"] = time.time()
        result["phase"] = phase(result.get("state"))
        if result.get("cancelled"):
            result["phase"] = "cancelled"
        elif config["kind"] == "bambu_lan" and result.get("state") == "RUNNING" and result.get("layer") == 0:
            result["phase"] = "preparing"
        if result.get("error") or result.get("error_code") not in (None, 0, "0"):
            result["ready_to_start"] = False
        result["requires_attention"] = result["phase"] in {"error", "paused"} or bool(result.get("error")) or bool(result.get("hms")) or (result.get("error_code") not in (None, 0, "0") and not result.get("cancelled"))
        return result

    def snapshot(self, name):
        from .camera import bambu_frame, http_frame, image_type
        config = self.config(name)
        options = config.get("options", {})
        if options.get("camera_url"):
            data = http_frame(options)
        elif config["kind"] == "bambu_lan" and options.get("camera_protocol") == "bambu_jpeg":
            data = bambu_frame(self.adapter(config))
        else:
            raise OrcaError("No supported camera configured. Set camera_url for an HTTP JPEG/PNG snapshot, or camera_protocol=bambu_jpeg for a P1/A1. RTSPS is not implemented.")
        suffix, mime = image_type(data)
        directory = self.base / "snapshots"
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = directory / (uuid.uuid4().hex + "." + suffix)
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as target:
            target.write(data)
        return {"printer": name, "path": str(path), "mime_type": mime, "bytes": len(data), "sha256": sha256(path),
                "received_at": time.time(), "freshness": "Received on a new request; camera capture time is unknown.",
                "physical_readiness_verified": False, "note": "Private local snapshot. Inspect visually; a picture cannot certify a clean plate or safe print."}

    def monitor(self, name, receipt_id=None):
        receipt = None
        if receipt_id is not None:
            receipt = read_json(self.base / "receipts" / f"{identifier(receipt_id)}.json")
            if receipt["printer"] != name or receipt["config"] != self.config(name):
                raise OrcaError("Receipt does not match the configured destination.")
        status = self.status(name)
        path = self.base / "monitor" / f"{identifier(name)}.json"
        previous = read_json(path) if path.exists() else {}
        tracked = {key: status.get(key) for key in ("state", "phase", "filename", "progress_percent", "layer", "error_code", "error", "hms", "requires_attention")}
        changed = [key for key in tracked if tracked[key] != previous.get(key)]
        write_json(path, tracked)
        result = {"printer": name, "status": status, "changed_fields": changed, "first_observation": not previous,
                  "background_monitoring": False, "note": "One read-only observation. Call again to follow progress; this tool does not schedule notifications."}
        if receipt:
            filename = str(status.get("filename") or "").replace("\\", "/").rsplit("/", 1)[-1]
            expected = receipt["remote"].replace("\\", "/").rsplit("/", 1)[-1]
            match = "unknown" if not filename else "match" if filename == expected else "different_job"
            result.update(receipt_id=receipt_id, job_match=match,
                          job_outcome=status["phase"] if match == "match" and status.get("telemetry_fresh", True) else "unknown")
        return result

    def preflight(self, job_id, artifact, name=None, expected_bed_type=None):
        from .preflight import review
        path, job = self.slicer.artifact(job_id, artifact)
        result = review(path, job, expected_bed_type)
        if name is not None:
            config = self.config(name)
            options = config.get("options", {})
            result["destination"] = {"name": name, "kind": config["kind"], "printer_profile": config["printer_profile"]}
            if job["printer_profile"] != config["printer_profile"]:
                result["errors"].append("Job printer/nozzle preset does not match the configured destination.")
            if config["kind"] != "file":
                extension = ".3mf" if config["kind"] == "bambu_lan" else ".gcode"
                if path.suffix.lower() != extension:
                    result["errors"].append(f"This connection requires a verified {extension} artifact.")
            else:
                result["warnings"].append("This destination requires manual file handoff; network upload/start is unavailable.")
            if config["kind"] == "bambu_lan":
                result["material_source"] = "AMS" if options.get("use_ams") else "external_spool"
                result["ams_mapping"] = options.get("ams_mapping", [])
                result["warnings"].append("AMS mapping uses zero-based tray indices and is configured intent, not a live check of loaded material.")
        result["checks_passed"] = not result["errors"]
        result["printer_contacted"] = False
        return result

    def upload(self, name, job_id, artifact, expected_bed_type=None):
        preflight = self.preflight(job_id, artifact, name, expected_bed_type)
        if preflight["errors"]:
            raise OrcaError(" ".join(preflight["errors"]))
        config = self.config(name)
        path, job = self.slicer.artifact(job_id, artifact)
        extension = ".3mf" if config["kind"] == "bambu_lan" else ".gcode"
        if path.suffix.lower() != extension:
            raise OrcaError(f"This connection requires a verified {extension} artifact.")
        if job["printer_profile"] != config["printer_profile"]:
            raise OrcaError("Job printer/nozzle preset does not match the configured destination.")
        adapter = self.adapter(config)
        if not adapter.status()["ready_to_start"]:
            raise OrcaError("Printer is busy, disconnected or not ready; upload was not attempted.")
        remote_name = f"hermes-{job_id}-{uuid.uuid4().hex[:8]}{extension}"
        details = adapter.validate_job(path, job) if hasattr(adapter, "validate_job") else {}
        remote = adapter.upload(path, remote_name)
        if not isinstance(remote, str) or not remote or any(c in remote for c in ("\r", "\n")) or ".." in remote.split("/"):
            raise OrcaError("Printer returned an invalid remote filename.")
        receipt_id = uuid.uuid4().hex
        receipt = {"id": receipt_id, "printer": name, "config": config, "job_id": job_id,
                   "artifact": artifact, "sha256": sha256(path), "remote": remote,
                   "uploaded_at": time.time(), "state": "uploaded", "details": details, "preflight": preflight}
        write_json(self.base / "receipts" / f"{receipt_id}.json", receipt)
        return {"receipt_id": receipt_id, "remote": remote, "print_started": False, "preflight": preflight,
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
        if config["kind"] == "bambu_lan":
            adapter.start(receipt["remote"], receipt["details"])
        else:
            adapter.start(receipt["remote"])
        receipt["state"] = "start_accepted"
        write_json(receipt_path, receipt)
        return {"receipt_id": receipt_id, "state": "start_accepted", "note": "Command accepted; poll printer status to verify actual printing."}

    def control(self, name, action, confirmed=False):
        if action not in {"pause", "resume", "cancel"}:
            raise OrcaError("Action must be pause, resume or cancel.")
        if confirmed is not True:
            raise OrcaError("Printer control requires explicit user intent.")
        config = self.config(name)
        adapter = self.adapter(config)
        record = None
        if config["kind"] == "bambu_lan":
            before = adapter.status()
            record = {"action": action, "config": config, "before": before["state"], "filename": before.get("filename"),
                      "issued_at": time.time(), "accepted": False}
            path = self.base / "controls" / f"{identifier(name)}.json"
            write_json(path, record)
        adapter.control(action)
        if record is not None:
            record["accepted"] = True
            write_json(path, record)
        return {"action": action, "state": "command_accepted", "next": "Poll status to verify."}
