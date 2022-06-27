# Copyright (C) 2022, François-Guillaume Fernandez.

# This program is licensed under the Apache License version 2.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0.txt> for full license details.


import json
from datetime import datetime
from pathlib import Path

shebang = ["#!usr/bin/python\n"]
blank_line = "\n"


def main(args):

    # Possible years
    current_year = datetime.now().year
    assert args.year <= current_year, f"Invalid first copyright year: {args.year}"

    with open("supported-licenses.json", "rb") as f:
        LICENSES = json.load(f)
    license_info = LICENSES[args.license]

    year_options = [f"{current_year}"] + [f"{year}-{current_year}" for year in range(args.year, current_year)]
    copyright_notices = [[f"# Copyright (C) {year_str}, {args.owner}.\n"] for year_str in year_options]
    license_notice = [
        f"# This program is licensed under the {license_info['name']}.\n",
        f"# See LICENSE or go to <{license_info['url']}> for full license details.\n",
    ]

    # Define all header options
    HEADERS = [
        shebang + [blank_line] + copyright_notice + [blank_line] + license_notice
        for copyright_notice in copyright_notices
    ] + [copyright_notice + [blank_line] + license_notice for copyright_notice in copyright_notices]

    IGNORED_FILES = args.ignores.split(",")
    FOLDERS = args.folders.split(",")

    invalid_files = []

    # For every python file in the repository
    for folder in FOLDERS:
        for source_path in Path(__file__).parent.parent.joinpath(folder).rglob("**/*.py"):
            if source_path.name not in IGNORED_FILES:
                # Parse header
                header_length = max(len(option) for option in HEADERS)
                current_header = []
                with open(source_path) as f:
                    for idx, line in enumerate(f):
                        current_header.append(line)
                        if idx == header_length - 1:
                            break
                # Validate it
                if not any(
                    "".join(current_header[: min(len(option), len(current_header))]) == "".join(option)
                    for option in HEADERS
                ):
                    invalid_files.append(source_path)

    if len(invalid_files) > 0:
        invalid_str = "\n- " + "\n- ".join(map(str, invalid_files))
        invalid_str += "\n\nYour header should look like:\n\n" + "".join(HEADERS[-1])
        raise AssertionError(f"Invalid header in the following files:{invalid_str}")


def parse_args():
    import argparse

    parser = argparse.ArgumentParser(
        description="Header validator for your Python files", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument("license", type=str, help="identifier of the license being used")
    parser.add_argument("owner", type=str, help="owner of the copyright")
    parser.add_argument("year", type=int, help="first copyright year of the project")
    parser.add_argument("--folders", type=str, default=".", help="folders to inspect")
    parser.add_argument("--ignores", type=str, default="", help="files to ignore")
    args = parser.parse_args()

    return args


if __name__ == "__main__":
    args = parse_args()
    main(args)
