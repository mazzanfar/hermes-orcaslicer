"""Opt-in stock CLI smoke test; synthetic cube only, never contacts a printer.

Run: python -m tests.live_slicer (or python tests/live_slicer.py from repo root
with PYTHONPATH=.). Output stays under ignored test-output/.
"""
import json
import time
from pathlib import Path

from tests.tools_harness import Tools
from orca_plugin.profiles import Catalog, roots
from orca_plugin.slicer import discover


def cube(path):
    v = [(x, y, z) for z in (0, 5) for y in (0, 5) for x in (0, 5)]
    faces = [(0, 2, 1), (1, 2, 3), (4, 5, 6), (5, 7, 6), (0, 1, 4), (1, 5, 4),
             (2, 6, 3), (3, 6, 7), (0, 4, 2), (2, 4, 6), (1, 3, 5), (3, 7, 5)]
    text = ["solid cube"]
    for face in faces:
        text += ["facet normal 0 0 0", "outer loop"]
        text += ["vertex " + " ".join(map(str, v[i])) for i in face]
        text += ["endloop", "endfacet"]
    path.write_text("\n".join(text + ["endsolid cube"]))


def wait_for_job(tools, job_id):
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        result = tools.call("orca_job", job_id=job_id)
        if result["state"] != "slicing":
            return result
        time.sleep(0.2)
    raise AssertionError("Tiny acceptance job exceeded two minutes")


def run():
    base = Path("test-output/cross-brand").resolve()
    base.mkdir(parents=True, exist_ok=True)
    model = base / "cube.stl"
    cube(model)
    source_bytes = model.read_bytes()
    tools = Tools(base)
    catalog = Catalog(roots(discover()))
    cases = [
        ("Prusa", "Prusa MK4 0.4 nozzle", "0.20mm Standard @MK4", "Prusa Generic PLA @MK4"),
        ("Creality", "Creality Ender-3 V3 0.4 nozzle", "0.20mm Standard @Creality Ender-3 V3", "Creality Generic PLA @Ender-3V3-all"),
        ("BBL", "Bambu Lab P1S 0.4 nozzle", "0.20mm Standard @BBL X1C", "Generic PLA"),
    ]
    results = []
    for vendor, machine, process, filament in cases:
        def preset(kind, name):
            return str(catalog.items[vendor, kind, name][0])
        job = tools.call("orca_prepare", source=str(model), machine=preset("machine", machine),
                         process=preset("process", process), filaments=[preset("filament", filament)], arrange=True, orient=True, bed_type="Textured PEI Plate")
        tools.call("orca_slice", job_id=job["id"])
        result = wait_for_job(tools, job["id"])
        if result["state"] == "sliced":
            assert result["printer_profile"] == machine
            for output in result["artifacts"]:
                review = tools.call("orca_preflight", job_id=job["id"], artifact=output["name"], expected_bed_type="Textured PEI Plate")
                assert review["checks_passed"], review
                assert review["bed_type"] == "Textured PEI Plate", review
                assert review["first_layer_bed_temperature"] is not None, review
            artifact = next(a for a in result["artifacts"] if a["name"].endswith(".gcode"))
            preview = tools.call("orca_preview", job_id=job["id"], artifact=artifact["name"])
            assert preview["segments"] > 0, preview
            last_layer = max(r["layer_markers"] for r in result["reports"])
            assert tools.call("orca_preview", job_id=job["id"], artifact=artifact["name"], layer=last_layer)["segments"] > 0
            # A fresh tool service must still read and export completed jobs.
            restarted = Tools(base)
            assert restarted.call("orca_job", job_id=job["id"])["state"] == "sliced"
            for output in result["artifacts"]:
                destination = base / (job["id"] + "-" + output["name"])
                exported = restarted.call("orca_export", job_id=job["id"], artifact=output["name"], destination=str(destination))
                assert exported["print_started"] is False
                assert destination.read_bytes() == Path(output["path"]).read_bytes()
                restarted.reject("orca_export", job_id=job["id"], artifact=output["name"], destination=str(destination))
            assert model.read_bytes() == source_bytes
        print(json.dumps({"printer": machine, "job": job["id"], "state": result["state"],
                          "error": result.get("error"), "reports": result.get("reports")}), flush=True)
        results.append(result)
        if vendor == "Prusa" and result["state"] == "sliced":
            project = next(a for a in result["artifacts"] if a["name"].endswith(".3mf"))["path"]
            before = Path(project).read_bytes()
            review = tools.call("orca_open_native", job_id=job["id"], artifact=Path(project).name)
            again = tools.call("orca_open_native", job_id=job["id"], artifact=Path(project).name)
            assert review["project"] == again["project"] and not review["launch_requested"]
            assert Path(review["project"]).read_bytes() == before
            inspected = tools.call("orca_inspect", source=project)
            object_id = inspected["objects"][0]["id"]
            edited = tools.call("orca_edit_project", source=project, destination=str(base / (job["id"] + "-edited.3mf")),
                               object_changes={object_id: {"wall_loops": 4}}, instance_changes={"0": {"move_mm": [5, 0, 0], "rotate_deg": [0, 0, 45], "scale": [1.2, 1, 1]}})
            assert Path(project).read_bytes() == before
            inspected = tools.call("orca_inspect", source=edited["project"])
            assert inspected["objects"][0]["settings"]["wall_loops"] == "4"
            edited_job = tools.call("orca_prepare", source=edited["project"])
            tools.call("orca_slice", job_id=edited_job["id"])
            edited_result = wait_for_job(tools, edited_job["id"])
            assert edited_result["state"] == "sliced", edited_result
            final_project = next(a["path"] for a in edited_result["artifacts"] if a["name"].endswith(".3mf"))
            assert tools.call("orca_inspect", source=final_project)["objects"][0]["settings"]["wall_loops"] == "4"
            results.append(edited_result)
            print(json.dumps({"editing_workflow": "passed", "job": edited_job["id"]}), flush=True)
    # Real Orca failure, rather than a mocked subprocess return code.
    broken = base / "invalid.stl"
    broken.write_text("This is not a triangulated mesh.\n")
    rejected = tools.call("orca_prepare", source=str(broken), machine=preset("machine", machine),
                          process=preset("process", process), filaments=[preset("filament", filament)], bed_type="Textured PEI Plate")
    tools.call("orca_slice", job_id=rejected["id"])
    failed = wait_for_job(tools, rejected["id"])
    assert failed["state"] == "failed", failed
    tools.reject("orca_export", job_id=rejected["id"], artifact="sliced.3mf", destination=str(base / "must-not-export.3mf"))
    assert not (base / "must-not-export.3mf").exists()
    print(json.dumps({"invalid_mesh_rejected": True}), flush=True)
    (base / "results.json").write_text(json.dumps(results, indent=2))
    return 0 if all(r["state"] == "sliced" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(run())
