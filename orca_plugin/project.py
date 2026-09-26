"""Edit a new Orca project copy; geometry payloads and unrelated settings are preserved."""
import math
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from .common import OrcaError, existing_file, sha256
from .profiles import MAX_MEMBER, project_settings, validate_changes

CORE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
ET.register_namespace("", CORE)
ET.register_namespace("p", "http://schemas.microsoft.com/3dmanufacturing/production/2015/06")
ET.register_namespace("BambuStudio", "http://schemas.bambulab.com/package/2021")


def xml(data):
    if len(data) > MAX_MEMBER or b"<!DOCTYPE" in data or b"<!ENTITY" in data:
        raise OrcaError("Project XML exceeds limits or contains unsupported declarations.")
    try:
        return ET.fromstring(data)
    except ET.ParseError as exc:
        raise OrcaError("Invalid project XML.") from exc


def vector(value, default, low, high):
    value = default if value is None else value
    if not isinstance(value, list) or len(value) != 3:
        raise OrcaError("Transforms require three numeric values: X, Y, Z.")
    if any(type(n) not in (int, float) or not math.isfinite(n) or not low <= n <= high for n in value):
        raise OrcaError("Transform values are outside supported bounds.")
    return value


def transform(item, edit):
    if set(edit) - {"move_mm", "rotate_deg", "scale"}:
        raise OrcaError("Unknown instance transform.")
    move = vector(edit.get("move_mm"), [0, 0, 0], -10000, 10000)
    rotate = vector(edit.get("rotate_deg"), [0, 0, 0], -360, 360)
    scale = vector(edit.get("scale"), [1, 1, 1], 0.01, 100)
    values = [float(v) for v in item.get("transform", "1 0 0 0 1 0 0 0 1 0 0 0").split()]
    if len(values) != 12 or not all(math.isfinite(n) for n in values):
        raise OrcaError("Invalid 3MF instance transform.")
    basis = [[values[row * 3 + col] * scale[row] for col in range(3)] for row in range(3)]
    for axis, angle in enumerate(rotate):
        c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
        a, b = ((1, 2), (2, 0), (0, 1))[axis]
        for row in basis:
            row[a], row[b] = row[a] * c - row[b] * s, row[a] * s + row[b] * c
    values = [v for row in basis for v in row] + [values[9 + i] + move[i] for i in range(3)]
    item.set("transform", " ".join(f"{v:.12g}" for v in values))
    item.set("auto_drop", "0")


def instances(source):
    with zipfile.ZipFile(source) as archive:
        info = archive.getinfo("3D/3dmodel.model")
        if info.file_size > MAX_MEMBER:
            raise OrcaError("Main model XML exceeds the 32 MB editing limit; use native Orca editing.")
        root = xml(archive.read(info))
    return [{"index": i, "object_id": item.get("objectid"), "transform": item.get("transform"), "printable": item.get("printable", "1")}
            for i, item in enumerate(root.findall(f"{{{CORE}}}build/{{{CORE}}}item"))]


def edit_project(source, destination, object_changes=None, instance_changes=None):
    src = existing_file(source, {".3mf"})
    dest = Path(destination).expanduser().resolve()
    if dest.suffix.lower() != ".3mf" or dest.exists():
        raise OrcaError("Choose a new .3mf destination; existing files are never overwritten.")
    object_changes, instance_changes = object_changes or {}, instance_changes or {}
    if not isinstance(object_changes, dict) or not isinstance(instance_changes, dict) or not (object_changes or instance_changes):
        raise OrcaError("Provide object_changes keyed by object id or instance_changes keyed by build index from orca_inspect.")
    settings = project_settings(src)
    nozzle = settings.get("nozzle_diameter", ["0.4"])
    diameter = min(map(float, nozzle if isinstance(nozzle, list) else [nozzle]))
    with zipfile.ZipFile(src) as archive:
        members = archive.infolist()
        if len(members) > 10000 or sum(i.file_size for i in members) > 1024 ** 3 or any(i.file_size > 512 * 1024 ** 2 for i in members):
            raise OrcaError("Project exceeds processing limits.")
        replacements = {}
        if object_changes:
            name = "Metadata/model_settings.config"
            if archive.getinfo(name).file_size > MAX_MEMBER:
                raise OrcaError("Object metadata exceeds editing limits.")
            root = xml(archive.read(name))
            objects = {obj.get("id"): obj for obj in root.findall("object")}
            for object_id, changes in object_changes.items():
                if object_id not in objects:
                    raise OrcaError("Unknown object id; inspect this exact project before editing.")
                changes = validate_changes(changes)
                for key in ("layer_height", "initial_layer_print_height"):
                    if float(changes.get(key, 0)) > diameter * 0.8:
                        raise OrcaError("Object layer height exceeds 80% of the nozzle diameter.")
                obj = objects[object_id]
                for key, value in changes.items():
                    nodes = [m for m in obj.findall("metadata") if m.get("key") == key]
                    if not nodes:
                        nodes = [ET.SubElement(obj, "metadata", {"key": key})]
                    for node in nodes:
                        node.set("value", value)
            replacements[name] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        if instance_changes:
            name = "3D/3dmodel.model"
            if archive.getinfo(name).file_size > MAX_MEMBER:
                raise OrcaError("Main model XML exceeds editing limits; use native Orca editing.")
            root = xml(archive.read(name))
            if root.get("unit", "millimeter") != "millimeter":
                raise OrcaError("Instance editing requires millimeter units.")
            items = root.findall(f"{{{CORE}}}build/{{{CORE}}}item")
            for index, edit in instance_changes.items():
                if not isinstance(index, str) or not index.isdigit() or int(index) >= len(items) or not isinstance(edit, dict):
                    raise OrcaError("Unknown instance index or invalid transform.")
                transform(items[int(index)], edit)
            replacements[name] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        dest.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation also prevents a racing process from overwriting the destination.
        with dest.open("xb") as output:
            try:
                with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as target:
                    for info in members:
                        # Cached toolpaths are stale after any edit. Orca will regenerate them.
                        if info.filename.lower().endswith((".gcode", ".gcode.md5")):
                            continue
                        target.writestr(info, replacements.get(info.filename, archive.read(info)))
            except Exception:
                output.close()
                dest.unlink(missing_ok=True)
                raise
    return {"project": str(dest), "sha256": sha256(dest), "objects_edited": list(object_changes),
            "instances_edited": list(instance_changes), "requires_reslice": True,
            "next": "Prepare and slice this new project; inspect plate assignment and full native preview before printing."}
