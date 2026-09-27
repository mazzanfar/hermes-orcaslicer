"""Run acceptance against installed code, outside the repository import path."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slicer", action="store_true", help="Run real slicing instead of protocol acceptance")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    work = repo / "test-output" / ("installed-" + uuid.uuid4().hex)
    shutil.copytree(repo / "tests", work / "tests", ignore=shutil.ignore_patterns("__pycache__"))
    env = dict(os.environ, HERMES_ORCA_HOME=str(work / "state"))
    env.pop("PYTHONPATH", None)
    probe = '''import importlib.metadata as m, json, pathlib, subprocess, sys
import orca_plugin
assert "site-packages" in pathlib.Path(orca_plugin.__file__).parts, orca_plugin.__file__
ep = next(e for e in m.entry_points(group="hermes_agent.plugins") if e.name == "orcaslicer")
assert callable(ep.load())
assert pathlib.Path(orca_plugin.__file__).with_name("SKILL.md").is_file()
import paho.mqtt.client
result = subprocess.run([sys.executable, "-m", "orca_plugin.cli", "orca_capabilities"], capture_output=True, text=True, check=True)
assert json.loads(result.stdout)["success"]
print("Installed package, entry point, skill, MQTT dependency and CLI verified.")
'''
    subprocess.run([sys.executable, "-c", probe], cwd=work, env=env, check=True)
    command = [sys.executable, "-m", "tests.live_slicer"] if args.slicer else [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]
    print("Acceptance artifacts:", work, flush=True)
    subprocess.run(command, cwd=work, env=env, check=True, timeout=600)


if __name__ == "__main__":
    main()
