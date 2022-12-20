# Copyright (C) 2022, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.


import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

SHEBANG = ["#!usr/bin/python\n"]
BLANK_LINE = "\n"
# https://raw.githubusercontent.com/spdx/license-list-data/v3.17/json/licenses.json
with open(Path(__file__).parent.absolute().joinpath("supported-licenses.json"), "rb") as f:
    raw_data = json.load(f)
LICENSES: Dict[str, Dict[str, str]] = {
    license["licenseId"]: {"name": license["name"], "urls": license["seeAlso"]} for license in raw_data["licenses"]
}


def get_header_options(license_id: str, owner: str, starting_year: int) -> List[List[str]]:

    # Year check
    current_year = datetime.now().year
    assert starting_year <= current_year, f"Invalid first copyright year: {starting_year}"

    # License check
    license_info = LICENSES.get(license_id)
    assert isinstance(license_info, dict), f"Invalid license identifier: {license_id}"

    # Owner check
    assert len(owner) > 0, "Please specify the copyright owner"

    # License file check
    assert Path("LICENSE").is_file(), "Unable to locate local copy of license text."

    # Header build
    year_options = [f"{current_year}"] + [f"{year}-{current_year}" for year in range(starting_year, current_year)]
    copyright_notices = [[f"# Copyright (C) {year_str}, {owner}.\n"] for year_str in year_options]
    license_notices = [
        [
            f"# This program is licensed under the {license_info['name']}.\n",
            f"# See LICENSE or go to <{url}> for full license details.\n",
        ]
        for url in license_info["urls"]
    ]

    return [
        SHEBANG + [BLANK_LINE] + copyright_notice + [BLANK_LINE] + license_notice
        for copyright_notice in copyright_notices
        for license_notice in license_notices
    ] + [
        copyright_notice + [BLANK_LINE] + license_notice
        for copyright_notice in copyright_notices
        for license_notice in license_notices
    ]


def main(args):

    # Check args & define all header options
    header_options = get_header_options(args.license, args.owner, args.year)

    ignored_files = args.ignore_files.split(",")
    ignored_folders = [Path(folder) for folder in args.ignore_folders.split(",")]
    folders = args.folders.split(",")

    invalid_files = []

    # For every python file in the repository
    for folder in folders:
        folder_path = Path(folder)
        assert folder_path.is_dir(), f"Invalid folder path: {folder}"
        for source_path in folder_path.rglob("**/*.py"):
            if source_path.name in ignored_files or any(folder in source_path.parents for folder in ignored_folders):
                continue
            # Parse header
            header_length = max(len(option) for option in header_options)
            current_header = []
            with open(source_path) as f:
                for idx, line in enumerate(f):
                    current_header.append(line)
                    if idx == header_length - 1:
                        break
            # Validate it
            if not any(
                "".join(current_header[: min(len(option), len(current_header))]) == "".join(option)
                for option in header_options
            ):
                invalid_files.append(source_path)

    if len(invalid_files) > 0:
        invalid_str = "\n- " + "\n- ".join(map(str, invalid_files))
        invalid_str += "\n\nYour header should look like:\n\n" + "".join(header_options[-1])
        raise AssertionError(f"Invalid header in the following files:{invalid_str}")


def parse_args():
    import argparse

    parser = argparse.ArgumentParser(
        description="Header validator for your Python files", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument("license", type=str, help="identifier of the license being used")
    parser.add_argument("owner", type=str, help="name of the copyright owner")
    parser.add_argument("year", type=int, help="first copyright year of the project")
    parser.add_argument("--folders", type=str, default=".", help="folders to inspect")
    parser.add_argument("--ignore-files", type=str, default="", help="files to ignore")
    parser.add_argument("--ignore-folders", type=str, default="", help="folders to ignore")
    args = parser.parse_args()

    return args


if __name__ == "__main__":
    args = parse_args()
    main(args)
