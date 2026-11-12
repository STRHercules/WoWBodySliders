import hashlib
import unittest

from shadowlands.analyze_live_samples import summarize


class CaptureTests(unittest.TestCase):
    def test_direct_call_uses_runtime_rva_and_truncation_is_visible(self):
        data = bytes.fromhex("e810000000c348")
        result = summarize(data, 0x1000)
        self.assertEqual(result["direct_calls"], [dict(site_rva=0x1000, target_rva=0x1015)])
        self.assertEqual(result["decoded_bytes"], 6)
        self.assertEqual(result["size"], 7)
        self.assertEqual(result["sha256"], hashlib.sha256(data).hexdigest())


if __name__ == "__main__":
    unittest.main()
