"""Portable SVG preview of linear extrusion moves at a chosen layer.

This is a review aid, not an implementation of a printer's G-code interpreter.
Unknown movement semantics are reported rather than silently certified.
"""
import re
from pathlib import Path

from .common import OrcaError


def layer_svg(gcode: Path, output: Path, layer=1):
    if type(layer) is not int or layer < 1:
        raise OrcaError("Layer must be a positive integer.")
    x = y = e = 0.0
    absolute = True
    absolute_e = True
    current_layer = 0
    segments = []
    unsupported = set()
    with gcode.open(errors="replace") as f:
        for raw in f:
            if raw.startswith("; CHANGE_LAYER") or raw.startswith(";LAYER_CHANGE"):
                current_layer += 1
                if current_layer > layer:
                    break
            code = raw.split(";", 1)[0].strip().upper()
            if not code:
                continue
            command = code.split()[0]
            words = {k: float(v) for k, v in re.findall(r"([XYZE])\s*(-?(?:\d+(?:\.\d*)?|\.\d+))", code)}
            if command == "G90":
                absolute = True
            elif command == "G91":
                absolute = False
            elif command == "M82":
                absolute_e = True
            elif command == "M83":
                absolute_e = False
            elif command == "G92":
                x, y, e = words.get("X", x), words.get("Y", y), words.get("E", e)
            elif command in {"G0", "G1", "G2", "G3"}:
                nx = words.get("X", x) if absolute else x + words.get("X", 0)
                ny = words.get("Y", y) if absolute else y + words.get("Y", 0)
                ne = words.get("E", e) if absolute_e else e + words.get("E", 0)
                if current_layer == layer and ne > e and (nx != x or ny != y):
                    if command in {"G2", "G3"}:
                        unsupported.add("G2/G3 arcs omitted")
                    elif len(segments) < 200000:
                        segments.append((x, y, nx, ny))
                    else:
                        raise OrcaError("Layer has too many segments for preview.")
                x, y, e = nx, ny, ne
            elif current_layer == layer and command in {"G20", "G28", "G53", "G54", "G55"}:
                unsupported.add(command + " coordinate effects not modeled")
    if not segments:
        raise OrcaError("No linear extrusion moves at this layer; inspect in OrcaSlicer instead.")
    xs = [p for s in segments for p in (s[0], s[2])]
    ys = [p for s in segments for p in (s[1], s[3])]
    minx, miny, maxx, maxy = min(xs), min(ys), max(xs), max(ys)
    paths = " ".join(f"M{x:.3f},{-y:.3f}L{nx:.3f},{-ny:.3f}" for x, y, nx, ny in segments)
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{minx-2} {-maxy-2} {maxx-minx+4} {maxy-miny+4}" width="1000" height="1000"><rect x="{minx-2}" y="{-maxy-2}" width="{maxx-minx+4}" height="{maxy-miny+4}" fill="#f5f7fa"/><path d="{paths}" fill="none" stroke="#147d92" stroke-width="0.25"/></svg>'
    output.write_text(svg)
    return {"preview": str(output), "layer": layer, "segments": len(segments),
            "extrusion_xy_bounds": [minx, miny, maxx, maxy], "warnings": sorted(unsupported),
            "note": "Linear extrusion preview only. For full geometry, arcs, tool offsets and support review, open the sliced 3MF in OrcaSlicer."}
