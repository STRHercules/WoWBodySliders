import json
from pathlib import Path
import unittest

from shadowlands import generate_profile


class ProfileTests(unittest.TestCase):
    def test_checked_in_profile_matches_audit(self):
        root = Path(__file__).resolve().parent
        report = json.loads((root / "exe-audit.json").read_text())
        self.assertEqual((root / "ClientProfile.h").read_text(), generate_profile.generate(report))
        report["sha256"] = "unknown"
        with self.assertRaises(ValueError):
            generate_profile.generate(report)


if __name__ == "__main__":
    unittest.main()
