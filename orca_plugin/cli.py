"""JSON command-line interface for diagnostics and reproducible local testing."""
import argparse
import json
import time

from . import Service, TOOLS


def main():
    parser = argparse.ArgumentParser(description="OrcaSlicer tools for Hermes")
    parser.add_argument("tool", choices=sorted(TOOLS))
    parser.add_argument("arguments", nargs="?", default="{}", help="JSON object")
    parser.add_argument("--wait", action="store_true", help="For orca_slice: wait for completion")
    args = parser.parse_args()
    if args.tool == "orca_slice" and not args.wait:
        parser.error("orca_slice requires --wait in the CLI (Hermes tools are asynchronous)")
    try:
        params = json.loads(args.arguments)
    except ValueError:
        parser.error("arguments must be a JSON object")
    service = Service()
    result = json.loads(service.handle(args.tool, params))
    if args.tool == "orca_slice" and result["success"]:
        # CLI must keep the worker alive; plugin calls run inside the Hermes process.
        while True:
            result = json.loads(service.handle("orca_job", {"job_id": params["job_id"]}))
            if not result["success"] or result["result"]["state"] != "slicing":
                break
            time.sleep(0.25)
    print(json.dumps(result, indent=2))
    payload = result.get("result")
    failed_job = isinstance(payload, dict) and payload.get("state") in {"failed", "unknown"}
    return 0 if result["success"] and not failed_job else 1


if __name__ == "__main__":
    raise SystemExit(main())
