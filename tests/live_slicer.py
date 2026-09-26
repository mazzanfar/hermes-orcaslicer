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


def run():
    base = Path("test-output/cross-brand").resolve()
    base.mkdir(parents=True, exist_ok=True)
    model = base / "cube.stl"
    cube(model)
    tools = Tools(base)
    catalog = Catalog(roots(discover()))
    cases = [
        ("Prusa", "Prusa MK4 0.4 nozzle", "0.20mm Standard @MK4", "Prusa Generic PLA @MK4"),
        ("Creality", "Creality Ender-3 V3 0.4 nozzle", "0.20mm Standard @Creality Ender-3 V3", "Creality Generic PLA @Ender-3V3-all"),
    ]
    results = []
    for vendor, machine, process, filament in cases:
        def preset(kind, name):
            return str(catalog.items[vendor, kind, name][0])
        job = tools.call("orca_prepare", source=str(model), machine=preset("machine", machine),
                         process=preset("process", process), filaments=[preset("filament", filament)])
        tools.call("orca_slice", job_id=job["id"])
        while True:
            result = tools.call("orca_job", job_id=job["id"])
            if result["state"] != "slicing":
                break
            time.sleep(0.2)
        if result["state"] == "sliced":
            assert result["printer_profile"] == machine
            artifact = next(a for a in result["artifacts"] if a["name"].endswith(".gcode"))
            preview = tools.call("orca_preview", job_id=job["id"], artifact=artifact["name"])
            assert preview["segments"] > 0, preview
            destination = base / (job["id"] + ".gcode")
            exported = tools.call("orca_export", job_id=job["id"], artifact=artifact["name"], destination=str(destination))
            assert exported["print_started"] is False
            assert destination.read_bytes() == Path(artifact["path"]).read_bytes()
        print(json.dumps({"printer": machine, "job": job["id"], "state": result["state"],
                          "error": result.get("error"), "reports": result.get("reports")}), flush=True)
        results.append(result)
    (base / "results.json").write_text(json.dumps(results, indent=2))
    return 0 if all(r["state"] == "sliced" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(run())
