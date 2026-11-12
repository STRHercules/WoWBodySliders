import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(os.name == "nt", "Windows native launcher tests")
class LauncherTests(unittest.TestCase):
    def test_missing_and_unknown_clients_are_not_launched(self):
        build = Path(__file__).resolve().parents[1] / "build/shadowlands/Release"
        launcher = build / "BodySliderShadowlandsAttach.exe"
        if not launcher.is_file():
            self.skipTest("Build the x64 Shadowlands launcher first")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "launcher.exe"
            shutil.copyfile(launcher, target)
            result = subprocess.run([str(target)], capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 2)
            log = root / "BodySliderShadowlandsAttach.log"
            self.assertIn("result=2", log.read_text())
            (root / "Wow.exe").write_bytes(b"MZ: not the supported game")
            (root / "BodySliderShadowlandsRuntime-0.2.4.dll").write_bytes(b"not a library")
            result = subprocess.run([str(target)], capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 5)
            self.assertIn(b"Nothing launched", result.stderr)
            self.assertIn("result=5", log.read_text())


if __name__ == "__main__":
    unittest.main()
