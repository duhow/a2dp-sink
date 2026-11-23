#!/bin/sh
# Run from the repository root inside the official ESPHome container.
set -eu

python -m unittest discover -s tests -v

python - <<'PY'
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, "tests")
from test_config import example_config, minimal_config
import yaml

for name, config in (("minimal", minimal_config()), ("full", example_config())):
    config["esphome"]["build_path"] = f"/build/{name}"
    # Stable config paths preserve ESPHome's incremental-build metadata.
    path = Path("/build/config") / f"{name}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(config, sort_keys=False))
    subprocess.run(["esphome", "compile", str(path)], check=True)
PY
