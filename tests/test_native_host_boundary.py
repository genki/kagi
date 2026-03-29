from __future__ import annotations

import unittest
from pathlib import Path


class NativeHostBoundaryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]
        cls.launcher_source = cls.root / "portable" / "launcher" / "kagi_launcher.c"
        cls.build_script = cls.root / "portable" / "launcher" / "build.sh"

    def test_vendored_portable_launcher_source_exists(self):
        self.assertTrue(self.launcher_source.exists())

    def test_vendored_portable_launcher_captures_current_cpython_host_boundary(self):
        source = self.launcher_source.read_text(encoding="utf-8")
        self.assertIn('%s/bin/python3', source)
        self.assertIn('%s/app/kagi_app.zip', source)
        self.assertIn('PYTHONHOME', source)
        self.assertIn('PYTHONPATH', source)
        self.assertIn('KAGI_HOME', source)
        self.assertIn('"kagi.host_entry"', source)
        self.assertIn('"failed to exec bundled python: %s\\n"', source)

    def test_launcher_build_script_exists_and_targets_vendored_source(self):
        script = self.build_script.read_text(encoding="utf-8")
        self.assertIn('kagi_launcher.c', script)
        self.assertIn('cc -D_GNU_SOURCE -D_POSIX_C_SOURCE=200809L -O2 -Wall -Wextra -std=c11', script)


if __name__ == "__main__":
    unittest.main()
