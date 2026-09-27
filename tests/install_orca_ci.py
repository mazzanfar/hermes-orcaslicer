"""Install a hash-pinned official Orca release into CI runner temporary storage.

Only for GitHub-hosted CI; never installs into a user's application directory.
"""
import hashlib
import os
from pathlib import Path
import platform
import plistlib
import shutil
import subprocess
import urllib.request
import zipfile

ASSETS = {
    "Linux": ("OrcaSlicer_Linux_AppImage_Ubuntu2404_V2.4.2.AppImage", "d12fb8c8eac1aecd2dfb6377acd48f994f8fa439ed5292fa532dd82880f029fd"),
    "Darwin": ("OrcaSlicer_Mac_universal_V2.4.2.dmg", "e15e7bb1b66214ec6e96b169b388004179c4f5f705effcdaf8c80d4992ee0366"),
    "Windows": ("OrcaSlicer_Windows_V2.4.2_x64_portable.zip", "feba3009dfb9d268779cca5758a1a5bc3b7d0722bf8fa48d5c57340de975d6be"),
}


def main():
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise SystemExit("This installer is only for disposable GitHub CI runners.")
    system = platform.system()
    name, digest = ASSETS[system]
    base = Path(os.environ["RUNNER_TEMP"]) / "orca-2.4.2"
    base.mkdir()
    archive = base / name
    url = "https://github.com/OrcaSlicer/OrcaSlicer/releases/download/v2.4.2/" + name
    with urllib.request.urlopen(url, timeout=120) as source, archive.open("wb") as target:
        shutil.copyfileobj(source, target)
    with archive.open("rb") as stream:
        assert hashlib.file_digest(stream, "sha256").hexdigest() == digest, "Orca release checksum mismatch"
    if system == "Linux":
        archive.chmod(0o755)
        subprocess.run([str(archive), "--appimage-extract"], cwd=base, stdout=subprocess.DEVNULL, check=True)
        executable = base / "squashfs-root/bin/orca-slicer"
        profiles = base / "squashfs-root/resources/profiles"
    elif system == "Darwin":
        result = subprocess.check_output(["hdiutil", "attach", "-readonly", "-nobrowse", "-plist", str(archive)])
        mount = next(Path(e["mount-point"]) for e in plistlib.loads(result)["system-entities"] if "mount-point" in e)
        try:
            app = next(mount.glob("*.app"))
            target = base / app.name
            shutil.copytree(app, target, symlinks=True)
        finally:
            subprocess.run(["hdiutil", "detach", str(mount)], check=True)
        executable = target / "Contents/MacOS/OrcaSlicer"
        profiles = target / "Contents/Resources/profiles"
    else:
        with zipfile.ZipFile(archive) as package:
            package.extractall(base / "portable")
        executable = next(p for p in (base / "portable").rglob("*.exe") if p.name.lower() in {"orca-slicer.exe", "orcaslicer.exe"})
        profiles = executable.parent / "resources/profiles"
    assert executable.is_file(), executable
    assert profiles.is_dir(), profiles
    with Path(os.environ["GITHUB_ENV"]).open("a", encoding="utf-8") as env:
        env.write(f"ORCA_SLICER_PATH={executable}\nORCA_PROFILES_DIR={profiles}\n")
    print(f"Verified OrcaSlicer 2.4.2 installed for {system}")


if __name__ == "__main__":
    main()
