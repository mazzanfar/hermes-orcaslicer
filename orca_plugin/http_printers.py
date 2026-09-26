"""PrusaLink v1 and RepRapFirmware 3 HTTP adapters; see docs/CONNECTIONS.md."""
import os
import re
import urllib.parse
from .common import OrcaError


def secret(options, name, default=None):
    variable = options.get(name)
    value = os.environ.get(variable) if variable else default
    if value is None:
        raise OrcaError("Set the configured printer credential environment variable.")
    return value


class PrusaLink:
    def __init__(self, http):
        self.http = http
        self.storage = http.config.get("options", {}).get("storage", "usb")

    def status(self):
        result = self.http.request("GET", "/api/v1/status")
        state = result.get("printer", {}).get("state", "UNKNOWN")
        return {"state": state, "ready_to_start": state in {"IDLE", "READY", "FINISHED", "STOPPED"},
                "job_id": result.get("job", {}).get("id"), "progress": result.get("job", {}).get("progress")}

    def upload(self, path, filename):
        if path.stat().st_size > 256 * 1024 * 1024:
            raise OrcaError("Use file export for uploads larger than 256 MB.")
        self.http.request("PUT", self.file_path(filename), path.read_bytes(), "application/octet-stream",
                          headers={"Print-After-Upload": "?0", "Overwrite": "?0"})
        return filename

    def file_path(self, filename):
        return "/api/v1/files/" + self.storage + "/" + urllib.parse.quote(filename, safe="")

    def start(self, remote):
        return self.http.request("POST", self.file_path(remote))

    def control(self, action):
        job = self.http.request("GET", "/api/v1/job")
        job_id = job.get("id")
        if type(job_id) is not int:
            raise OrcaError("PrusaLink reports no current job to control.")
        endpoint = f"/api/v1/job/{job_id}"
        return self.http.request("DELETE" if action == "cancel" else "PUT", endpoint + ("" if action == "cancel" else "/" + action))


class Duet:
    def __init__(self, http):
        self.http = http
        self.headers = None

    def request(self, method, path, data=None):
        if self.headers is None:
            password = secret(self.http.config.get("options", {}), "password_env", "reprap")
            reply = self.http.request("GET", "/rr_connect?" + urllib.parse.urlencode({"password": password, "sessionKey": "yes"}))
            if reply.get("err") != 0:
                raise OrcaError("Duet refused the session; check credentials and available sessions.")
            self.headers = {"X-Session-Key": str(reply["sessionKey"])} if "sessionKey" in reply else {}
        try:
            result = self.http.request(method, path, data, "application/octet-stream" if data is not None else None, headers=self.headers)
            if isinstance(result, dict) and result.get("err", 0) != 0:
                raise OrcaError("Duet rejected the request.")
            return result
        finally:
            # Close only our unique session; older IP-based sessions may be shared with DWC.
            if self.headers.get("X-Session-Key"):
                try:
                    self.http.request("GET", "/rr_disconnect", headers=self.headers)
                except OrcaError:
                    pass
            self.headers = None

    def status(self):
        state = self.request("GET", "/rr_model?key=state.status&flags=f").get("result", "unknown")
        return {"state": state, "ready_to_start": state == "idle"}

    def upload(self, path, filename):
        if path.stat().st_size > 256 * 1024 * 1024:
            raise OrcaError("Use file export for uploads larger than 256 MB.")
        self.request("POST", "/rr_upload?" + urllib.parse.urlencode({"name": "0:/gcodes/" + filename}), path.read_bytes())
        return filename

    def command(self, code):
        result = self.request("GET", "/rr_gcode?" + urllib.parse.urlencode({"gcode": code}))
        if "buff" not in result:
            raise OrcaError("Duet did not acknowledge command buffering; check printer status.")
        return result

    def start(self, remote):
        if not re.fullmatch(r"[a-zA-Z0-9_.-]+", remote):
            raise OrcaError("Invalid Duet remote filename.")
        return self.command(f'M32 "0:/gcodes/{remote}"')

    def control(self, action):
        return self.command({"pause": "M25", "resume": "M24", "cancel": "M0"}[action])


class Flashforge:
    """Modern port-8898 HTTP interface; external-spool/single-tool jobs only."""
    def __init__(self, http):
        self.http = http
        self.options = http.config["options"]

    def auth(self):
        return {"serialNumber": self.options["serial"], "checkCode": secret(self.options, "access_code_env")}

    def checked(self, result):
        if result.get("code") != 0:
            raise OrcaError("Flashforge rejected the request; check its screen, serial and access code.")
        return result

    def request(self, path, **body):
        return self.checked(self.http.request("POST", path, {**self.auth(), **body}))

    def status(self):
        detail = self.request("/detail").get("detail", {})
        state = detail.get("status", "unknown")
        return {"state": state, "ready_to_start": state == "ready" and not detail.get("errorCode"),
                "progress": detail.get("printProgress"), "filename": detail.get("printFileName"), "firmware": detail.get("firmwareVersion")}

    def validate_job(self, path, job):
        with path.open(errors="replace") as source:
            for line in source:
                match = re.match(r"^T(\d+)\b", line.strip())
                if match and 0 < int(match[1]) < 64:
                    raise OrcaError("Flashforge HTTP currently supports single-tool external-spool jobs. Use native Orca for material-station mapping.")
        return {}

    def upload(self, path, filename):
        headers = {**self.auth(), "fileSize": str(path.stat().st_size), "printNow": "false", "levelingBeforePrint": "false",
                   "flowCalibration": "false", "useMatlStation": "false", "gcodeToolCnt": "1", "materialMappings": "W10="}
        self.checked(self.http.upload("/uploadGcode", path, filename, {}, headers=headers, field_name="gcodeFile"))
        return filename

    def start(self, remote):
        return self.request("/printGcode", fileName=remote, levelingBeforePrint=self.options.get("bed_levelling", True), useMatlStation=False)

    def control(self, action):
        return self.request("/control", payload={"cmd": "jobCtl_cmd", "args": {"jobID": "", "action": "continue" if action == "resume" else action}})
