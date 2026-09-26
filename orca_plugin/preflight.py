"""Review verified sliced settings, without claiming physical readiness."""
import io
import zipfile

from .common import OrcaError
from .profiles import BED_TYPES
from .slicer import analyze_gcode


PLATE_TEMPERATURE = dict(zip(
    ("Cool Plate", "Engineering Plate", "High Temp Plate", "Textured PEI Plate", "Textured Cool Plate", "Supertack Plate"),
    ("cool_plate_temp", "eng_plate_temp", "hot_plate_temp", "textured_plate_temp", "textured_cool_plate_temp", "supertack_plate_temp")))


def review(path, job, expected_bed_type=None):
    if expected_bed_type is not None and (not isinstance(expected_bed_type, str) or expected_bed_type not in BED_TYPES):
        raise OrcaError("Choose a supported expected_bed_type matching the physical plate.")
    if path.suffix.lower() == ".3mf":
        member = f'Metadata/plate_{job.get("plate", 1)}.gcode'
        try:
            with zipfile.ZipFile(path) as archive:
                if archive.namelist().count(member) != 1:
                    raise OrcaError("Preflight needs exactly one embedded G-code file for the selected plate.")
                if archive.getinfo(member).file_size > 512 * 1024 * 1024:
                    raise OrcaError("Selected plate exceeds the preflight inspection limit.")
                with archive.open(member) as source, io.TextIOWrapper(source, errors="replace") as text:
                    report = analyze_gcode(path, stream=text)
        except (zipfile.BadZipFile, KeyError) as exc:
            raise OrcaError("Cannot inspect the sliced 3MF for preflight.") from exc
    elif path.suffix.lower() == ".gcode":
        report = analyze_gcode(path)
    else:
        raise OrcaError("Preflight requires verified G-code or a sliced 3MF.")
    metadata = report["metadata"]
    bed = metadata.get("curr_bed_type")
    temperature_key = PLATE_TEMPERATURE.get(bed)
    errors, warnings = [], []
    for key in ("curr_bed_type", "nozzle_diameter", "filament_type", "nozzle_temperature"):
        if not metadata.get(key):
            warnings.append(f"Sliced metadata does not report {key}; verify it in native Orca.")
    if expected_bed_type is not None and bed != expected_bed_type:
        errors.append(f"Sliced bed type {bed or 'unknown'} does not match expected {expected_bed_type}. Prepare and re-slice with the correct bed_type.")
    if expected_bed_type is None:
        warnings.append("Physical plate type has not been compared; supply expected_bed_type when known.")
    embedded_profile = metadata.get("printer_settings_id")
    if embedded_profile and embedded_profile.strip('"') != job["printer_profile"]:
        errors.append("Sliced printer profile does not match the job's bound printer profile.")
    return {"job_id": job["id"], "artifact": path.name, "printer_profile": job["printer_profile"],
            "bed_type": bed, "expected_bed_type": expected_bed_type,
            "nozzle_diameter": metadata.get("nozzle_diameter"), "filament_type": metadata.get("filament_type"),
            "filament_preset": metadata.get("filament_settings_id"),
            "nozzle_temperature": metadata.get("nozzle_temperature"),
            "first_layer_nozzle_temperature": metadata.get("nozzle_temperature_initial_layer"),
            "bed_temperature": metadata.get(temperature_key) if temperature_key else metadata.get("bed_temperature"),
            "first_layer_bed_temperature": metadata.get("first_layer_bed_temperature") or metadata.get((temperature_key or "bed_temperature") + "_initial_layer"),
            "estimates": {k: v for k, v in metadata.items() if "time" in k or "filament used" in k or "total filament" in k},
            "layers": report["layer_markers"], "errors": errors, "warnings": warnings,
            "checks_passed": not errors, "physical_readiness_verified": False, "print_started": False,
            "limitations": "Slicer metadata, not a firmware interpreter or a camera inspection. Review toolpaths, loaded material and the clear/clean plate separately."}
