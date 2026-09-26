"""Stock OrcaSlicer CLI integration. Never writes the user's Orca presets."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
import zipfile
from pathlib import Path

from .common import OrcaError, existing_file, identifier, read_json, sha256, write_json
from .profiles import BED_TYPES, Catalog, inspect_project, project_settings, roots, validate_changes

REQUIRED_FLAGS = ("--slice", "--outputdir", "--export-3mf", "--datadir")


def discover() -> Path:
    override = os.environ.get("ORCA_SLICER_PATH")
    if override:
        return existing_file(override)
    candidates = [shutil.which(n) for n in ("orca-slicer", "OrcaSlicer", "orca-slicer.exe")]
    candidates += ["/Applications/OrcaSlicer.app/Contents/MacOS/OrcaSlicer",
                   str(Path.home() / "Applications/OrcaSlicer.app/Contents/MacOS/OrcaSlicer")]
    for base in (os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")):
        if base:
            candidates.append(str(Path(base) / "OrcaSlicer/orca-slicer.exe"))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate).resolve()
    raise OrcaError("OrcaSlicer not found. Install it and set ORCA_SLICER_PATH to its executable (not the .app directory).")


def diagnose():
    exe = discover()
    try:
        proc = subprocess.run([str(exe), "--help"], capture_output=True, text=True,
                              errors="replace", timeout=20, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OrcaError("OrcaSlicer could not run. On Linux a display/Xvfb may be required; see troubleshooting.") from exc
    output = proc.stdout + proc.stderr
    missing = [flag for flag in REQUIRED_FLAGS if flag not in output]
    return {"executable": str(exe), "version": next((line for line in output.splitlines() if "OrcaSlicer" in line), "unknown"),
            "cli_ready": proc.returncode == 0 and not missing, "missing_flags": missing,
            "profile_roots": [str(p) for p in roots(exe)], "platform": sys.platform}


class Slicer:
    def __init__(self, base: Path):
        self.base = base
        self._lock = threading.RLock()
        self._processes = {}

    def directory(self, job_id):
        path = self.base / "jobs" / identifier(job_id)
        if not (path / "job.json").is_file():
            raise OrcaError("Unknown job id.")
        return path

    def prepare(self, source, changes=None, machine=None, process=None, filaments=None, plate=1, arrange=False, orient=False, bed_type=None):
        src = existing_file(source, {".3mf", ".stl", ".obj", ".step", ".stp"})
        if type(plate) is not int or plate < 1:
            raise OrcaError("Choose a single plate number starting at 1. Slice each plate as a separate job.")
        if type(arrange) is not bool or type(orient) is not bool:
            raise OrcaError("arrange and orient must be booleans.")
        changes = validate_changes(changes or {})
        if bed_type is not None:
            if not isinstance(bed_type, str) or bed_type not in BED_TYPES:
                raise OrcaError("Choose a supported Orca bed_type; inspect the physical plate first.")
            changes["curr_bed_type"] = bed_type
        exe = discover()
        catalog = Catalog(roots(exe))
        resolved = {}
        for kind, value in (("machine", machine), ("process", process)):
            if value:
                resolved[kind] = catalog.resolve(existing_file(value, {".json"}), kind)
                identity = "printer_settings_id" if kind == "machine" else "print_settings_id"
                resolved[kind][identity] = resolved[kind]["name"]
        filament_data = [catalog.resolve(existing_file(f, {".json"}), "filament") for f in (filaments or [])]
        for filament in filament_data:
            filament["filament_settings_id"] = [filament["name"]]
        if src.suffix.lower() != ".3mf" and (len(resolved) != 2 or not filament_data):
            raise OrcaError("Raw models require machine, process and filament preset paths. Search presets first.")
        settings = {}
        if src.suffix.lower() == ".3mf":
            try:
                settings = project_settings(src)
            except OrcaError:
                if len(resolved) != 2 or not filament_data:
                    raise
        if settings and machine:
            raise OrcaError("Changing a project's printer can leave incompatible object settings. Export its models, then prepare with the new printer presets.")
        settings.update(resolved.get("machine", {}))
        settings.update(resolved.get("process", {}))
        settings.update(changes)
        if "process" in resolved:
            resolved["process"].update(changes)
        nozzle = settings.get("nozzle_diameter", [0.4])
        try:
            diameter = float(nozzle[0] if isinstance(nozzle, list) else nozzle)
            if float(settings.get("layer_height", 0.2)) > diameter * 0.8:
                raise OrcaError("Layer height exceeds 80% of the selected nozzle diameter.")
        except (ValueError, TypeError, IndexError) as exc:
            raise OrcaError("Cannot validate nozzle diameter and layer height.") from exc
        machine_name = settings.get("printer_settings_id") or resolved.get("machine", {}).get("name")
        if not machine_name:
            raise OrcaError("A named printer profile is required to bind output to the correct printer.")
        compatible = resolved.get("process", {}).get("compatible_printers", [])
        if compatible and machine_name not in compatible:
            raise OrcaError("The process preset does not list this printer as compatible.")
        for filament in filament_data:
            compatible = filament.get("compatible_printers", [])
            if compatible and machine_name not in compatible:
                raise OrcaError(f"Filament preset {filament.get('name')} is incompatible with this printer.")
        job_id = uuid.uuid4().hex
        directory = self.base / "jobs" / job_id
        directory.mkdir(parents=True)
        copy = directory / ("input" + src.suffix.lower())
        shutil.copyfile(src, copy)
        if settings and src.suffix.lower() == ".3mf" and changes:
            temporary = directory / "updated.3mf"
            with zipfile.ZipFile(copy) as z, zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as dest:
                if len(z.infolist()) > 10000 or sum(i.file_size for i in z.infolist()) > 1024 * 1024 * 1024:
                    raise OrcaError("Project exceeds the 1 GB/10,000 member processing limit.")
                for info in z.infolist():
                    if info.file_size > 512 * 1024 * 1024:
                        raise OrcaError("Project member too large; maximum is 512 MB.")
                    data = z.read(info)
                    if info.filename == "Metadata/project_settings.config":
                        original = json.loads(data)
                        original.update(changes)
                        data = json.dumps(original).encode()
                    dest.writestr(info, data)
            os.replace(temporary, copy)
        elif changes:
            resolved.setdefault("process", {}).update(changes)
        settings_files = []
        for kind, value in resolved.items():
            path = directory / f"{kind}.json"
            write_json(path, value)
            settings_files.append(str(path))
        fila_files = []
        for index, value in enumerate(filament_data):
            path = directory / f"filament-{index}.json"
            write_json(path, value)
            fila_files.append(str(path))
        job = {"id": job_id, "state": "prepared", "created_at": time.time(),
               "input": str(copy), "source_name": src.name, "source_sha256": sha256(src),
               "input_sha256": sha256(copy), "printer_profile": machine_name,
               "plate": plate, "bed_type": settings.get("curr_bed_type"),
               "arrange": arrange, "orient": orient, "changes": changes, "executable": str(exe),
               "settings_files": settings_files, "filament_files": fila_files,
               "note": "Inspect object overrides and previews before printing. No printer contacted."}
        write_json(directory / "job.json", job)
        return job

    def _update(self, directory, **fields):
        with self._lock:
            job = read_json(directory / "job.json")
            job.update(fields)
            write_json(directory / "job.json", job)
            return job

    def slice(self, job_id):
        directory = self.directory(job_id)
        with self._lock:
            job = read_json(directory / "job.json")
            if job["state"] != "prepared":
                raise OrcaError("Only a prepared job can be sliced. Prepare a new job to retry or change settings.")
            if sha256(Path(job["input"])) != job["input_sha256"]:
                raise OrcaError("Prepared input changed. Prepare a new job.")
            output = directory / "output"
            output.mkdir()
            args = [job["executable"], "--datadir", str(directory / "orca-data"),
                    "--slice", str(job["plate"]), "--outputdir", str(output),
                    "--export-3mf", "sliced.3mf"]
            if job["settings_files"]:
                args += ["--load-settings", ";".join(job["settings_files"])]
            if job["filament_files"]:
                args += ["--load-filaments", ";".join(job["filament_files"])]
            if job.get("arrange"):
                args += ["--arrange", "1"]
            if job.get("orient"):
                args += ["--orient", "1", "--ensure-on-bed"]
            args += [job["input"]]
            self._update(directory, state="slicing", started_at=time.time(), command=args)
            thread = threading.Thread(target=self._run, args=(directory, args), daemon=True)
            thread.start()
        return {"id": job_id, "state": "slicing", "next": "Poll orca_job; slicing does not start the printer."}

    def _run(self, directory, args):
        try:
            with (directory / "slice.log").open("wb") as log:
                proc = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT,
                                        stdin=subprocess.DEVNULL, start_new_session=os.name != "nt")
                with self._lock:
                    self._processes[directory.name] = proc
                try:
                    code = proc.wait(timeout=1800)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                    raise OrcaError("Slicing exceeded 30 minutes; process terminated.")
            if code != 0:
                raise OrcaError(f"OrcaSlicer exited with code {code}. Inspect slice.log; no output is approved.")
            output = directory / "output"
            artifacts = []
            # Never extract a ZIP member's path: use a controlled local filename.
            existing_hashes = {sha256(p) for p in output.glob("*.gcode")}
            for archive in list(output.glob("*.3mf")):
                with zipfile.ZipFile(archive) as z:
                    for index, info in enumerate(z.infolist()):
                        if info.filename.lower().endswith(".gcode"):
                            if info.file_size > 512 * 1024 * 1024:
                                raise OrcaError("G-code exceeds the 512 MB artifact limit.")
                            target = output / f"extracted-{index}.gcode"
                            with z.open(info) as source, target.open("wb") as dest:
                                shutil.copyfileobj(source, dest)
                            digest = sha256(target)
                            if digest in existing_hashes:
                                target.unlink()
                            else:
                                existing_hashes.add(digest)
            for path in sorted(output.iterdir()):
                if path.is_file() and path.suffix.lower() in {".3mf", ".gcode", ".png"}:
                    artifacts.append({"name": path.name, "path": str(path), "sha256": sha256(path), "bytes": path.stat().st_size})
            gcodes = [a for a in artifacts if a["name"].endswith(".gcode")]
            if not gcodes:
                raise OrcaError("OrcaSlicer produced no G-code. This version/build may not support CLI slicing.")
            reports = [analyze_gcode(Path(a["path"])) for a in gcodes]
            logtext = (directory / "slice.log").read_text(errors="replace")
            warnings = [line[:500] for line in logtext.splitlines() if re.search(r"\b(warning|error)\b", line, re.I)][-50:]
            self._update(directory, state="sliced", finished_at=time.time(), artifacts=artifacts,
                         reports=reports, warnings=warnings,
                         note="Slicing succeeded; this is not a guarantee of fit, adhesion or mechanical strength.")
        except Exception as exc:
            message = str(exc) if isinstance(exc, OrcaError) else f"Slicing failed ({type(exc).__name__}); inspect slice.log."
            self._update(directory, state="failed", error=message, finished_at=time.time())
        finally:
            with self._lock:
                self._processes.pop(directory.name, None)

    def job(self, job_id):
        directory = self.directory(job_id)
        job = read_json(directory / "job.json")
        if job["state"] == "slicing" and job_id not in self._processes and time.time() - job.get("started_at", 0) > 30:
            # A restart loses ownership. Never treat an orphan's partial output as printable.
            return dict(job, state="unknown", note="Worker is no longer owned by this session. Inspect process/output; prepare a new job after it stops.")
        return job

    def artifact(self, job_id, name):
        job = self.job(job_id)
        if job["state"] != "sliced":
            raise OrcaError("Job has not successfully finished slicing.")
        item = next((a for a in job["artifacts"] if a["name"] == name), None)
        if not item or sha256(Path(item["path"])) != item["sha256"]:
            raise OrcaError("Artifact is missing or changed. Re-slice before exporting or printing.")
        return Path(item["path"]), job

    def open_native(self, job_id, artifact, launch=False):
        source, job = self.artifact(job_id, artifact)
        if source.suffix.lower() != ".3mf":
            raise OrcaError("Select the sliced .3mf artifact for full native preview and editing.")
        if type(launch) is not bool:
            raise OrcaError("launch must be a boolean.")
        directory = self.directory(job_id) / "review"
        directory.mkdir(exist_ok=True)
        copy = directory / "review.3mf"
        if not copy.exists():
            with copy.open("xb") as out, source.open("rb") as inp:
                shutil.copyfileobj(inp, out)
        marker = directory / "launch-requested"
        launched = marker.exists()
        if launch and not launched:
            exe = discover()
            args = [str(exe), str(copy)]
            if sys.platform == "darwin":
                args = ["open", "-a", str(exe.parent.parent.parent), str(copy)]
            try:
                with marker.open("x"):
                    pass
            except FileExistsError:
                launched = True
            else:
                try:
                    with (directory / "native.log").open("wb") as log:
                        process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=log,
                                                   stderr=subprocess.STDOUT, start_new_session=os.name != "nt")
                    try:
                        code = process.wait(timeout=1)
                        if code != 0:
                            raise OrcaError(f"Orca GUI exited with code {code}; inspect native.log in the review directory.")
                    except subprocess.TimeoutExpired:
                        pass
                    launched = True
                except Exception:
                    marker.unlink(missing_ok=True)
                    raise
        return {"project": str(copy), "launch_requested": launched, "print_started": False,
                "next": "Open this editable copy in Orca's existing window. Prepare provides full object/plate editing; Preview provides full toolpaths. Save edits here, then prepare and re-slice. Repeated calls reuse this copy and never launch another window. Launch is not proof of visual review."}

    def export(self, job_id, name, destination):
        source, job = self.artifact(job_id, name)
        dest = Path(destination).expanduser().resolve()
        if dest.suffix.lower() != source.suffix.lower():
            raise OrcaError("Destination extension must match the artifact.")
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            with dest.open("xb") as out, source.open("rb") as inp:
                shutil.copyfileobj(inp, out)
        except FileExistsError as exc:
            raise OrcaError("Destination already exists; choose a new filename.") from exc
        return {"exported": str(dest), "sha256": sha256(dest), "printer_profile": job["printer_profile"], "print_started": False}


def analyze_gcode(path: Path, stream=None):
    """Read slicer comments, not arbitrary command effects; expose uncertainty."""
    summary = {}
    layers = 0
    from contextlib import nullcontext
    with (nullcontext(stream) if stream is not None else path.open(errors="replace")) as f:
        for line in f:
            if line.startswith("; model printing time:"):
                for part in line.lstrip("; ").split(";"):
                    if ":" in part:
                        key, value = part.split(":", 1)
                        summary[key.strip()] = value.strip()
            if line.startswith("; CHANGE_LAYER") or line.startswith(";LAYER_CHANGE"):
                layers += 1
            if line.startswith(";") and "=" in line:
                key, value = line[1:].split("=", 1)
                key = key.strip()
                if key in {"curr_bed_type", "filament_type", "filament_settings_id", "nozzle_temperature",
                           "nozzle_temperature_initial_layer", "first_layer_bed_temperature", "bed_temperature",
                           "textured_plate_temp", "textured_plate_temp_initial_layer", "cool_plate_temp",
                           "cool_plate_temp_initial_layer", "hot_plate_temp", "hot_plate_temp_initial_layer",
                           "eng_plate_temp", "eng_plate_temp_initial_layer", "textured_cool_plate_temp",
                           "textured_cool_plate_temp_initial_layer", "supertack_plate_temp", "supertack_plate_temp_initial_layer"} or any(k in key for k in ("estimated printing time", "estimated first layer", "total estimated time", "filament used", "total filament", "total layer number", "printer_settings_id", "nozzle_diameter", "gcode_flavor")):
                    summary[key] = value.strip()[:300]
    return {"file": path.name, "metadata": summary, "layer_markers": layers,
            "limitations": "Metadata only; no claim that arbitrary G-code is safe or geometrically valid."}
