"""Opt-in, read-only hardware acceptance for any configured printer protocol.

Run python -m tests.live_printer --name PRINTER [--camera] [--receipt ID].
Never uploads, starts, controls, heats or moves a printer. Reports stay local.
"""
import argparse
import json
import platform
import time
import uuid
from pathlib import Path

from orca_plugin.common import home, write_json
from tests.tools_harness import Tools


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--state-dir", type=Path, default=home())
    parser.add_argument("--camera", action="store_true")
    parser.add_argument("--receipt")
    args = parser.parse_args()
    tools = Tools(args.state_dir.resolve())
    report = {"schema": 1, "observed_at": time.time(), "os": platform.system(), "python": platform.python_version(),
              "checks": {}, "not_tested": ["upload", "start", "pause", "resume", "cancel", "physical_quality"],
              "note": "Private local evidence from one configured device. Do not infer support for other models/firmware."}
    try:
        monitored = tools.call("orca_monitor", name=args.name, **({"receipt_id": args.receipt} if args.receipt else {}))
        status = monitored["status"]
        report["checks"]["status"] = {"passed": status.get("phase") not in {"unknown", "manual_handoff"},
                                       "state": status.get("state"), "phase": status.get("phase"),
                                       "firmware": status.get("firmware"),
                                       "fields_available": sorted(k for k, v in status.items() if v is not None),
                                       "job_match": monitored.get("job_match"), "job_outcome": monitored.get("job_outcome")}
    except AssertionError as exc:
        report["checks"]["status"] = {"passed": False, "error": str(exc)}
    if args.camera:
        try:
            snapshot = tools.call("orca_camera_snapshot", name=args.name)
            report["checks"]["camera"] = {"passed": True, "mime_type": snapshot["mime_type"], "bytes": snapshot["bytes"],
                                           "sha256": snapshot["sha256"], "visual_inspection_completed": False}
        except AssertionError as exc:
            report["checks"]["camera"] = {"passed": False, "error": str(exc)}
    destination = args.state_dir.resolve() / "validation" / (uuid.uuid4().hex + ".json")
    write_json(destination, report)
    print(json.dumps({"report": str(destination), "checks": report["checks"], "no_print_commands_sent": True}))
    return 0 if all(check["passed"] for check in report["checks"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(run())
