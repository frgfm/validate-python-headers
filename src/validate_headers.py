# Copyright (C) 2022, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.


import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Union

SHEBANG = ["#!usr/bin/python\n"]
BLANK_LINE = "\n"
# https://raw.githubusercontent.com/spdx/license-list-data/v3.17/json/licenses.json
with open(Path(__file__).parent.absolute().joinpath("supported-licenses.json"), "rb") as f:
    raw_data = json.load(f)
LICENSES: Dict[str, Dict[str, str]] = {
    license["licenseId"]: {"name": license["name"], "urls": license["seeAlso"]} for license in raw_data["licenses"]
}


def get_header_options(
    owner: str, starting_year: int, license_id: Union[str, None], license_notice: Union[str, None]
) -> List[List[str]]:

    # Year check
    current_year = datetime.now().year
    if starting_year > current_year:
        raise ValueError(f"Invalid first copyright year: {starting_year}")

    # Owner check
    if len(owner) == 0:
        raise ValueError("Please specify the copyright owner")

    # License check
    license_notice_str = None
    if isinstance(license_id, str):
        license_info = LICENSES.get(license_id)
        if not isinstance(license_info, dict):
            raise KeyError(f"Invalid license identifier: {license_id}")
        # License file check
        if not Path("LICENSE").is_file():
            raise FileNotFoundError("Unable to locate local copy of license text.")
    elif isinstance(license_notice, str):
        if not Path(license_notice).is_file():
            raise FileNotFoundError("Unable to locate the text of the license notice.")
        with open(license_notice, "r") as f:
            license_notice_str = f.readlines()
    else:
        raise ValueError("One of the following args needs to be specified: 'license_id', 'license_notice'")

    # Header build
    year_options = [f"{current_year}"] + [f"{year}-{current_year}" for year in range(starting_year, current_year)]
    copyright_notices = [[f"# Copyright (C) {year_str}, {owner}.\n"] for year_str in year_options]
    license_notices = (
        [
            [
                f"# This program is licensed under the {license_info['name']}.\n",
                f"# See LICENSE or go to <{url}> for full license details.\n",
            ]
            for url in license_info["urls"]
        ]
        if isinstance(license_id, str)
        else [license_notice_str]
    )

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
    header_options = get_header_options(args.owner, args.year, args.license, args.license_notice)

    ignored_files = args.ignore_files.split(",")
    ignored_folders = [Path(folder) for folder in args.ignore_folders.split(",")]
    folders = args.folders.split(",")

    invalid_files = []

    # For every python file in the repository
    for folder in folders:
        folder_path = Path(folder)
        if not folder_path.is_dir():
            raise FileNotFoundError(f"Invalid folder path: {folder}")
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

    parser.add_argument("owner", type=str, help="name of the copyright owner")
    parser.add_argument("year", type=int, help="first copyright year of the project")
    parser.add_argument("--license", type=str, default=None, help="identifier of the license being used")
    parser.add_argument("--folders", type=str, default=".", help="folders to inspect")
    parser.add_argument("--ignore-files", type=str, default="", help="files to ignore")
    parser.add_argument("--ignore-folders", type=str, default="", help="folders to ignore")
    parser.add_argument("--license-notice", type=str, default=None, help="path to custom license notice")
    args = parser.parse_args()

    return args


if __name__ == "__main__":
    args = parse_args()
    main(args)
