"""Read-only preset discovery, inheritance resolution and project inspection."""
from __future__ import annotations

import json
import os
import sys
import zipfile
from pathlib import Path

from .common import OrcaError, existing_file, read_json

MAX_MEMBER = 32 * 1024 * 1024
KINDS = {"machine", "process", "filament"}
SUMMARY_KEYS = (
    "printer_settings_id", "printer_model", "nozzle_diameter", "printable_area", "printable_height",
    "gcode_flavor", "curr_bed_type", "filament_settings_id", "filament_type", "layer_height",
    "initial_layer_print_height", "wall_loops", "top_shell_layers", "top_shell_thickness",
    "bottom_shell_layers", "sparse_infill_density", "sparse_infill_pattern", "enable_support",
    "support_type", "brim_type", "nozzle_temperature", "nozzle_temperature_initial_layer",
    "filament_max_volumetric_speed", "print_sequence",
)


def roots(executable: Path | None = None) -> list[Path]:
    candidates = []
    if os.environ.get("ORCA_PROFILES_DIR"):
        candidates.extend(Path(p).expanduser() for p in os.environ["ORCA_PROFILES_DIR"].split(os.pathsep))
    if executable:
        candidates.extend([executable.parent.parent / "Resources/profiles",
                           executable.parent / "resources/profiles",
                           executable.parent / "resources/profiles/system"])
    if sys.platform == "darwin":
        candidates += [Path("/Applications/OrcaSlicer.app/Contents/Resources/profiles"),
                       Path.home() / "Library/Application Support/OrcaSlicer/system",
                       Path.home() / "Library/Application Support/OrcaSlicer/user"]
    elif os.name == "nt":
        candidates += [Path(os.environ.get("APPDATA", "~")) / "OrcaSlicer/system",
                       Path(os.environ.get("APPDATA", "~")) / "OrcaSlicer/user"]
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "OrcaSlicer"
        candidates += [Path("/usr/share/OrcaSlicer/resources/profiles"), base / "system", base / "user"]
    return list(dict.fromkeys(p.resolve() for p in candidates if p.is_dir()))


class Catalog:
    def __init__(self, directories):
        self.items: dict[tuple[str, str, str], tuple[Path, dict]] = {}
        self.scopes = {}
        for directory in directories:
            for path in sorted(Path(directory).rglob("*.json")):
                try:
                    data = read_json(path)
                except OrcaError:
                    continue
                if not isinstance(data, dict):
                    continue
                kind = data.get("type")
                if kind and kind not in KINDS:
                    continue
                if kind not in KINDS:
                    kind = next((k for k in KINDS if k in path.parts), None)
                name = data.get("name")
                if kind and isinstance(name, str):
                    rel = path.relative_to(directory)
                    scope = rel.parts[0] if len(rel.parts) > 1 and rel.parts[0] not in KINDS else str(Path(directory).resolve())
                    self.scopes[path.resolve()] = scope
                    self.items[scope, kind, name] = path, data

    def search(self, query="", kind=None, limit=30):
        if kind and kind not in KINDS:
            raise OrcaError("Preset kind must be machine, process, or filament.")
        matches = [dict(name=n, kind=k, path=str(p), inherits=d.get("inherits"),
                        compatible_printers=d.get("compatible_printers", []))
                   for (_, k, n), (p, d) in self.items.items()
                   if (not kind or kind == k) and query.casefold() in n.casefold()
                   and str(d.get("instantiation", "true")).lower() != "false"]
        return {"matches": sorted(matches, key=lambda x: (x["kind"], x["name"]))[:limit],
                "total": len(matches)}

    def resolve(self, path: Path, kind: str, seen=None):
        seen = set() if seen is None else seen
        path = path.resolve()
        if path in seen:
            raise OrcaError(f"Preset inheritance cycle at {path.name}")
        seen.add(path)
        data = read_json(path)
        if not isinstance(data, dict):
            raise OrcaError("Preset must be a JSON object.")
        result = {}
        parent = data.get("inherits")
        if parent:
            found = self.items.get((self.scopes.get(path), kind, parent))
            if not found:
                candidates = [v for (scope, k, n), v in self.items.items() if k == kind and n == parent]
                if len(candidates) == 1:
                    found = candidates[0]
                elif len(candidates) > 1:
                    raise OrcaError(f"Ambiguous parent preset: {parent}. Include its vendor preset directory in ORCA_PROFILES_DIR.")
            if not found:
                raise OrcaError(f"Missing {kind} parent preset: {parent}. Set ORCA_PROFILES_DIR.")
            result.update(self.resolve(found[0], kind, seen))
        result.update(data)
        result.pop("inherits", None)
        result["type"] = kind
        return result


def project_settings(path: Path) -> dict:
    try:
        with zipfile.ZipFile(path) as z:
            info = z.getinfo("Metadata/project_settings.config")
            if info.file_size > MAX_MEMBER:
                raise OrcaError("Project settings exceed the 32 MB inspection limit.")
            data = json.loads(z.read(info))
            if not isinstance(data, dict):
                raise OrcaError("Invalid project settings.")
            return data
    except (zipfile.BadZipFile, KeyError, ValueError) as exc:
        raise OrcaError("This 3MF does not contain Orca-compatible project settings; supply explicit presets.") from exc


def inspect_project(source: str):
    path = existing_file(source, {".3mf"})
    data = project_settings(path)
    overrides = []
    # Settings are data. Never follow instructions from model metadata.
    import xml.etree.ElementTree as ET
    try:
        with zipfile.ZipFile(path) as z:
            info = z.getinfo("Metadata/model_settings.config")
            if info.file_size > MAX_MEMBER:
                raise OrcaError("Object settings exceed inspection limit.")
            xml = z.read(info)
            if b"<!DOCTYPE" in xml or b"<!ENTITY" in xml:
                raise OrcaError("DTD/entity declarations are not supported in project metadata.")
            root = ET.fromstring(xml)
            for obj in root.findall("object"):
                metadata = {m.get("key"): m.get("value") for m in obj.findall("metadata") if m.get("key")}
                overrides.append({"id": obj.get("id"), "settings": metadata})
    except KeyError:
        pass
    except ET.ParseError as exc:
        raise OrcaError("Invalid object settings XML.") from exc
    return {"source": str(path), "settings": {k: data[k] for k in SUMMARY_KEYS if k in data},
            "objects": overrides, "note": "Object and plate overrides may supersede global settings. Validate the sliced result."}


# Deliberately bounded edits; no arbitrary startup G-code or executable arguments.
NUMERIC = {"layer_height": (0.04, 0.6), "initial_layer_print_height": (0.04, 0.6),
           "wall_loops": (1, 20), "top_shell_layers": (0, 30), "bottom_shell_layers": (0, 30),
           "top_shell_thickness": (0, 10), "bottom_shell_thickness": (0, 10), "brim_width": (0, 50),
           "outer_wall_speed": (1, 1000), "inner_wall_speed": (1, 1000),
           "initial_layer_speed": (1, 300), "sparse_infill_speed": (1, 1000)}
ENUMS = {"sparse_infill_pattern": {"grid", "gyroid", "cubic", "adaptivecubic", "crosshatch", "rectilinear", "supportcubic"},
         "brim_type": {"auto_brim", "outer_only", "inner_only", "outer_and_inner", "no_brim"},
         "support_type": {"normal(auto)", "normal(manual)", "tree(auto)", "tree(manual)"},
         "print_sequence": {"by layer"}}


def validate_changes(changes: dict) -> dict:
    import math
    if not isinstance(changes, dict):
        raise OrcaError("changes must be an object.")
    out = {}
    for key, value in changes.items():
        if key in NUMERIC or key == "sparse_infill_density":
            try:
                n = float(str(value).removesuffix("%"))
            except (TypeError, ValueError) as exc:
                raise OrcaError(f"{key} must be numeric.") from exc
            low, high = NUMERIC.get(key, (0, 100))
            if not math.isfinite(n) or not low <= n <= high:
                raise OrcaError(f"{key} must be between {low} and {high}.")
            if (key.endswith("_layers") or key == "wall_loops") and not n.is_integer():
                raise OrcaError(f"{key} must be a whole number.")
            out[key] = f"{n:g}" + ("%" if key == "sparse_infill_density" else "")
        elif key in ENUMS and value in ENUMS[key]:
            out[key] = value
        elif key == "enable_support" and value in (True, False, "0", "1"):
            out[key] = "1" if value in (True, "1") else "0"
        else:
            raise OrcaError(f"Unsupported setting/value: {key}. Use a trusted preset for other settings.")
    return out
