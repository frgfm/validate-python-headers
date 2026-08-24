# Copyright (C) 2024-2026, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pyyaml>=6.0",
# ]
# ///

from pathlib import Path

import yaml


def main():
    # Retrieve & parse all deps files
    deps_dict = {"uv": []}
    # Parse github/workflows/...
    for workflow_file in Path(".github/workflows").glob("*.yml"):
        with workflow_file.open("r") as f:
            workflow = yaml.safe_load(f)
            if "env" in workflow and "UV_VERSION" in workflow["env"]:
                deps_dict["uv"].append({
                    "file": str(workflow_file),
                    "version": workflow["env"]["UV_VERSION"].lstrip("v"),
                })

    # Assert all deps are in sync
    troubles = []
    for dep, versions in deps_dict.items():
        versions_ = {v["version"] for v in versions}
        if len(versions_) != 1:
            inv_dict = {v: set() for v in versions_}
            for version in versions:
                inv_dict[version["version"]].add(version["file"])
            troubles.extend([
                f"{dep}:",
                "\n".join(f"- '{v}': {', '.join(files)}" for v, files in inv_dict.items()),
            ])

    if len(troubles) > 0:
        raise AssertionError("Some dependencies are out of sync:\n\n" + "\n".join(troubles))


if __name__ == "__main__":
    main()
