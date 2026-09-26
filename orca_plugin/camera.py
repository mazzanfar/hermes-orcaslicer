"""Explicit, bounded camera snapshots. No discovery, streaming or TLS bypass."""
import socket
import ssl
import struct
import time
import urllib.error
import urllib.parse
import urllib.request

from .common import OrcaError

MAX_IMAGE = 8 * 1024 * 1024


def image_type(data):
    if data.startswith(b"\xff\xd8") and data.endswith(b"\xff\xd9"):
        return "jpg", "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n") and data.endswith(b"IEND\xaeB`\x82"):
        return "png", "image/png"
    raise OrcaError("Camera did not return a complete JPEG or PNG snapshot.")


def bambu_frame(adapter):
    from .http_printers import secret
    deadline = time.monotonic() + 20
    def exact(sock, count):
        result = bytearray()
        while len(result) < count:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError
            sock.settimeout(remaining)
            part = sock.recv(min(65536, count - len(result)))
            if not part:
                raise EOFError
            result.extend(part)
        return bytes(result)
    try:
        password = secret(adapter.options, "access_code_env").encode("ascii")
        if not 1 <= len(password) <= 32:
            raise OrcaError("Camera access code must be 1–32 ASCII bytes.")
        with socket.create_connection((adapter.host, adapter.options.get("camera_port", 6000)), timeout=10) as raw:
            with adapter.tls().wrap_socket(raw) as sock:
                sock.sendall(struct.pack("<IIII32s32s", 0x40, 0x3000, 0, 0, b"bblp", password))
                size, _, _, _ = struct.unpack("<IIII", exact(sock, 16))
                if not 0 < size <= MAX_IMAGE:
                    raise OrcaError("Camera frame exceeds the snapshot size limit or has an invalid header.")
                data = exact(sock, size)
                image_type(data)
                return data
    except (OSError, EOFError, UnicodeError) as exc:
        raise OrcaError("Cannot read the verified Bambu JPEG camera. Check camera support, LAN access and credentials; TLS verification remains enabled.") from exc


def http_frame(options):
    # Camera credentials are separate; never forward printer credentials.
    from .http_printers import secret
    from .printers import NoRedirect
    request = urllib.request.Request(options["camera_url"], headers={"Accept": "image/jpeg, image/png", "Cache-Control": "no-cache"})
    if options.get("camera_api_key_env"):
        request.add_header("X-Api-Key", secret(options, "camera_api_key_env"))
    opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    try:
        with opener.open(request, timeout=15) as response:
            deadline, data = time.monotonic() + 20, bytearray()
            while len(data) <= MAX_IMAGE:
                if time.monotonic() >= deadline:
                    raise TimeoutError
                part = response.read1(min(65536, MAX_IMAGE + 1 - len(data)))
                if not part:
                    break
                data.extend(part)
            if len(data) > MAX_IMAGE:
                raise OrcaError("Camera snapshot exceeds the 8 MB limit.")
            data = bytes(data)
            image_type(data)
            return data
    except (OSError, urllib.error.URLError) as exc:
        raise OrcaError("Camera snapshot request failed. Check the explicit snapshot URL and separate camera credentials.") from exc
