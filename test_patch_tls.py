from pathlib import Path
import struct
import tempfile
import unittest

import pefile
from shadowlands import patch_tls


class PatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path(__file__).resolve().parents[1] / "Wow-Shadowlands.exe"
        if not cls.source.is_file():
            raise unittest.SkipTest("Requires supplied executable")
        cls.original = cls.source.read_bytes()
        cls.patched = patch_tls.patch_bytes(cls.original)

    def test_exact_restore_and_fingerprint(self):
        self.assertEqual(patch_tls.restore_bytes(self.patched), self.original)
        self.assertEqual(patch_tls.sha256(self.patched), "17f0e43c06a2240f52552436c09379290677765d2983380553a9a9c5a7076b14")
        self.assertEqual(self.source.read_bytes(), self.original)
        identity = (Path(__file__).resolve().parent / "ClientIdentity.h").read_text()
        self.assertIn(patch_tls.sha256(self.patched), identity)

    def test_preserves_startup_directories_and_only_changes_one_code_site(self):
        original = pefile.PE(data=self.original, fast_load=True)
        patched = pefile.PE(data=self.patched, fast_load=True)
        try:
            self.assertEqual(patched.OPTIONAL_HEADER.AddressOfEntryPoint, original.OPTIONAL_HEADER.AddressOfEntryPoint)
            self.assertEqual([d.__pack__() for d in patched.OPTIONAL_HEADER.DATA_DIRECTORY],
                             [d.__pack__() for d in original.OPTIONAL_HEADER.DATA_DIRECTORY])
            self.assertEqual(patched.OPTIONAL_HEADER.DllCharacteristics, original.OPTIONAL_HEADER.DllCharacteristics)
            site = original.get_offset_from_rva(patch_tls.SITE_RVA)
            headers = original.OPTIONAL_HEADER.SizeOfHeaders
            self.assertEqual(self.patched[headers:site], self.original[headers:site])
            self.assertEqual(self.patched[site + 9:len(self.original)], self.original[site + 9:])
            self.assertEqual(self.patched[site], 0xE9)
            destination = patch_tls.SITE_RVA + 5 + struct.unpack_from("<i", self.patched, site + 1)[0]
            self.assertEqual(destination, patched.sections[-1].VirtualAddress)
            self.assertTrue(patched.sections[-1].Characteristics & 0x20000000)
            self.assertFalse(patched.sections[-1].Characteristics & 0x80000000)
            self.assertEqual(patched.generate_checksum(), patched.OPTIONAL_HEADER.CheckSum)
        finally:
            original.close(); patched.close()

    def test_tampering_unknown_build_and_overwrite_are_rejected(self):
        for data in (b"MZ", self.original[:-1], self.patched):
            with self.assertRaises(ValueError): patch_tls.patch_bytes(data)
        changed = bytearray(self.patched); changed[0x1000] ^= 1
        for data in (changed, self.patched[:-1]):
            with self.assertRaises(ValueError): patch_tls.restore_bytes(data)
        with tempfile.TemporaryDirectory() as temporary:
            existing = Path(temporary) / "exists.exe"; existing.write_bytes(b"keep")
            with self.assertRaises(ValueError): patch_tls.write_copy(self.source, existing)
            with self.assertRaises(ValueError): patch_tls.write_copy(self.source, self.source)
            self.assertEqual(existing.read_bytes(), b"keep")


if __name__ == "__main__": unittest.main()
