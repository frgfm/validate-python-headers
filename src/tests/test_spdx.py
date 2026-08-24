# Copyright (C) 2026, François-Guillaume Fernandez.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

import hashlib
import json
import unittest
from pathlib import Path

from support import WorkspaceTestCase

from validate_headers import core

CURRENT_SHA256 = "f728c534d8bd1044fc515a2ddb2292be99559021d830bfa3281be0bcd36302ee"


class SpdxTestCase(WorkspaceTestCase):
    def test_snapshot_version_digest_and_compatibility_delta(self):
        snapshot_path = Path(core.__file__).with_name("supported-licenses.json")
        compatibility_path = Path(core.__file__).with_name("legacy-license-notices.json")
        snapshot = snapshot_path.read_bytes()
        compatibility = json.loads(compatibility_path.read_text(encoding="utf-8"))

        self.assertEqual(core.SPDX_DATA["licenseListVersion"], "3.28.0")
        self.assertEqual(len(core.SPDX_DATA["licenses"]), 727)
        self.assertEqual(hashlib.sha256(snapshot).hexdigest(), CURRENT_SHA256)
        self.assertEqual(compatibility["baseline_ref"], "94972478f38d080eadd37f098f771eb4cd235ae4")
        self.assertEqual(compatibility["baseline_version"], "3.17")
        self.assertEqual(len(compatibility["licenses"]), 29)

    def test_every_generated_v317_compatibility_notice_is_accepted(self):
        for license_id, item in core.LEGACY_LICENSES.items():
            with self.subTest(license_id=license_id):
                settings = self.settings(license=license_id)
                policy = core.build_policy(settings, 2030)
                for url in item["urls"]:
                    expected = (
                        f"# This program is licensed under the {item['name']}.\n"
                        f"# See LICENSE or go to <{url}> for full license details.\n"
                    )
                    self.assertIn(expected, policy.license_notices)
                if item["urls"]:
                    canonical = (
                        f"# This program is licensed under the {item['name']}.\n"
                        f"# See LICENSE or go to <{item['urls'][0]}> for full license details.\n"
                    )
                    self.assertEqual(policy.license_notices[0], canonical)

    def test_new_spdx_identifier_is_available(self):
        policy = core.build_policy(self.settings(license="3D-Slicer-1.0"), 2030)
        self.assertTrue(policy.license_notices)


if __name__ == "__main__":
    unittest.main()
