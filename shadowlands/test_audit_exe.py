import hashlib
import os
from pathlib import Path
import struct
import unittest

import pefile

from shadowlands import audit_exe


def fixture():
    """Minimal PE32+ with one name/function pair and an x64 runtime function."""
    data = bytearray(0x800)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<HHIIIHH", data, 0x84, 0x8664, 3, 0, 0, 0, 240, 0x22)
    optional = 0x98
    struct.pack_into("<H", data, optional, 0x20B)
    struct.pack_into("<Q", data, optional + 24, 0x140000000)
    struct.pack_into("<II", data, optional + 32, 0x1000, 0x200)
    struct.pack_into("<II", data, optional + 56, 0x4000, 0x200)
    struct.pack_into("<I", data, optional + 108, 16)
    struct.pack_into("<II", data, optional + 112 + 3 * 8, 0x3000, 12)
    for index, (name, rva, raw, flags) in enumerate((
        (b".text", 0x1000, 0x200, 0x60000020),
        (b".rdata", 0x2000, 0x400, 0x40000040),
        (b".pdata", 0x3000, 0x600, 0x40000040),
    )):
        struct.pack_into("<8sIIIIIIHHI", data, optional + 240 + index * 40,
                         name, 0x200, rva, 0x200, raw, 0, 0, 0, 0, flags)
    data[0x200:0x204] = bytes.fromhex("488bc1c3")
    data[0x410:0x419] = b"UnitGUID\0"
    struct.pack_into("<QQ", data, 0x440, 0x140002010, 0x140001000)
    struct.pack_into("<III", data, 0x600, 0x1000, 0x1004, 0x3020)
    data[0x620] = 1
    return data


class AuditTests(unittest.TestCase):
    def candidates(self, data):
        pe = pefile.PE(data=bytes(data))
        try:
            return audit_exe.registration_candidates(pe, ("UnitGUID", "Missing"))
        finally:
            pe.close()

    def test_pairs_use_rvas_and_disassemble_x64(self):
        result = self.candidates(fixture())
        candidate, = result["UnitGUID"]["candidates"]
        self.assertEqual(candidate["pair_rva"], 0x2040)
        self.assertEqual(candidate["function_rva"], 0x1000)
        self.assertEqual(candidate["prefix_disassembly"][-1]["mnemonic"], "ret")
        self.assertEqual(result["Missing"], dict(string_rvas=[], candidates=[]))

    def test_non_function_and_non_executable_targets_rejected(self):
        for target in (0x140001001, 0x140002000, 0, 0xFFFFFFFFFFFFFFFF):
            data = fixture()
            struct.pack_into("<Q", data, 0x448, target)
            self.assertEqual(self.candidates(data)["UnitGUID"]["candidates"], [])
        data = fixture()
        struct.pack_into("<I", data, 0x98 + 240 + 36, 0x40000040)
        self.assertEqual(self.candidates(data)["UnitGUID"]["candidates"], [])

    def test_unmapped_overlay_and_partial_pairs_are_ignored(self):
        data = fixture()
        data[0x440:0x450] = bytes(16)
        data.extend(struct.pack("<QQ", 0x140002010, 0x140001000))
        struct.pack_into("<Q", data, 0x5F8, 0x140002010)
        self.assertEqual(self.candidates(data)["UnitGUID"]["candidates"], [])

    def test_unknown_build_rejected(self):
        for data in (b"", bytes(fixture())):
            with self.assertRaisesRegex(ValueError, "Unsupported executable"):
                audit_exe.audit(data)

    def test_table_context_and_tls_validation(self):
        data = fixture()
        optional = 0x98
        struct.pack_into("<II", data, optional + 112 + 9 * 8, 0x2100, 40)
        struct.pack_into("<QQQQII", data, 0x500, 0, 0, 0, 0x140002180, 0, 0)
        struct.pack_into("<QQ", data, 0x580, 0x140001000, 0)
        pe = pefile.PE(data=bytes(data))
        try:
            anchors = audit_exe.registration_candidates(pe, ("UnitGUID",))
            table, = audit_exe.registration_tables(pe, anchors)
            self.assertEqual(table["entries"], [dict(pair_rva=0x2040, name="UnitGUID", function_rva=0x1000)])
            self.assertFalse(table["callable_verified"])
            self.assertEqual(audit_exe.tls_callbacks(pe), [0x1000])
            pe.DIRECTORY_ENTRY_TLS.struct.AddressOfCallBacks = 0x1
            with self.assertRaisesRegex(ValueError, "outside file-backed"):
                audit_exe.tls_callbacks(pe)
        finally:
            pe.close()


class SuppliedExeTests(unittest.TestCase):
    def test_pinned_executable(self):
        path = Path(os.environ.get("BODYSLIDER_SHADOWLANDS_EXE",
                                  Path(__file__).resolve().parents[1] / "Wow-Shadowlands.exe"))
        if not path.is_file():
            self.skipTest("Set BODYSLIDER_SHADOWLANDS_EXE to the supplied 9.2.7.45745 executable")
        data = path.read_bytes()
        before = hashlib.sha256(data).hexdigest()
        result = audit_exe.audit(data)
        self.assertEqual(result["sha256"], before)
        self.assertEqual(result["version"], [9, 2, 7, 45745])
        self.assertTrue(result["aslr"])
        self.assertTrue(result["anchors"]["UnitGUID"]["candidates"])
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)


if __name__ == "__main__":
    unittest.main()
