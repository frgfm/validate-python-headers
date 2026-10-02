# Copyright (C) 2026, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

from hashlib import sha256
from pathlib import Path
from urllib.request import urlopen

FONT_DIR = Path(__file__).resolve().parent.parent / "docs/assets/fonts"
FONT_VERSION = "5.3.0"
FONTS = (
    (
        "manrope-latin-wght-normal.woff2",
        "@fontsource-variable/manrope",
        "a30ddcd349703aff7464c34bef3fffdff405ee50c113440d7c8693c02d210972",
    ),
    (
        "ibm-plex-sans-latin-wght-normal.woff2",
        "@fontsource-variable/ibm-plex-sans",
        "e2291e842cf5af167122a22881a740c7f2dda7716f1e8cd76680264f4a859470",
    ),
    (
        "ibm-plex-mono-latin-400-normal.woff2",
        "@fontsource/ibm-plex-mono",
        "08949f728dc52d528e69b1667d15c89a5686a4ee9a296ff90983985f99c380f7",
    ),
)


def main():
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    downloaded = 0
    for filename, package, expected in FONTS:
        target = FONT_DIR / filename
        if target.is_file() and sha256(target.read_bytes()).hexdigest() == expected:
            continue
        url = f"https://cdn.jsdelivr.net/npm/{package}@{FONT_VERSION}/files/{filename}"
        with urlopen(url, timeout=30) as response:
            content = response.read()
        if sha256(content).hexdigest() != expected:
            raise ValueError(f"SHA-256 mismatch for {filename}; documentation build stopped.")
        target.write_bytes(content)
        downloaded += 1
    print(f"Prepared {len(FONTS)} documentation fonts ({downloaded} downloaded).")


if __name__ == "__main__":
    main()
