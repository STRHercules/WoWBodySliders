import hashlib
import os
from pathlib import Path
import struct
import tempfile
import unittest

import patcher


STOCK = Path(os.environ.get("BODYSLIDER_STOCK_EXE", Path(__file__).resolve().parent / "local/Wow.exe"))


class PatcherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not STOCK.is_file():
            raise unittest.SkipTest("Set BODYSLIDER_STOCK_EXE to the supported original Wow.exe")
        cls.original = STOCK.read_bytes()
        cls.patched = patcher.patch_bytes(cls.original)

    def test_restore_is_byte_identical(self):
        self.assertEqual(patcher.restore_bytes(self.patched), self.original)
        self.assertEqual(STOCK.read_bytes(), self.original)

    def test_unknown_or_already_patched_input_rejected(self):
        for candidate in (b"MZ", self.original[:-1], self.patched):
            with self.subTest(size=len(candidate)), self.assertRaises(ValueError):
                patcher.patch_bytes(candidate)

    def test_malformed_layout_rejected(self):
        for candidate in (b"", b"MZ" + b"\0" * 62, self.original[:900]):
            with self.subTest(size=len(candidate)), self.assertRaises(ValueError):
                patcher.pe_layout(candidate)

    def test_tampered_patched_file_rejected(self):
        changed = bytearray(self.patched)
        changed[0x1000] ^= 1
        with self.assertRaisesRegex(ValueError, "has changed"):
            patcher.restore_bytes(changed)
        with self.assertRaises(ValueError):
            patcher.restore_bytes(self.patched[:-1])

    def test_output_never_overwrites_source_or_existing_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            existing = Path(temporary) / "existing.exe"
            existing.write_bytes(b"keep")
            with self.assertRaises(ValueError):
                patcher.write_copy(STOCK, existing)
            with self.assertRaises(ValueError):
                patcher.write_copy(STOCK, STOCK)
            self.assertEqual(existing.read_bytes(), b"keep")

    def test_files_round_trip(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "Wow-BodySlider.exe"
            restored = Path(temporary) / "Wow-original.exe"
            patcher.write_copy(STOCK, output)
            patcher.write_copy(output, restored, restore=True)
            self.assertEqual(restored.read_bytes(), self.original)

    def test_original_code_and_resources_unchanged(self):
        original_layout = patcher.pe_layout(self.original)
        header_size = original_layout["headers_size"]
        self.assertEqual(self.patched[header_size:len(self.original)], self.original[header_size:])
        layout = patcher.pe_layout(self.patched)
        self.assertEqual(layout["count"], original_layout["count"] + 1)
        self.assertEqual(self.patched[layout["optional"] + 128:layout["optional"] + 136], b"\0" * 8)

    def test_pe_parser_and_stub_disassembly(self):
        try:
            import capstone
            import pefile
        except ImportError:
            self.skipTest("Optional pefile/capstone verification packages are not installed")
        original = pefile.PE(data=self.original)
        patched = pefile.PE(data=self.patched)
        self.assertEqual(patched.OPTIONAL_HEADER.CheckSum, patched.generate_checksum())
        self.assertEqual(patched.FILE_HEADER.NumberOfSections, original.FILE_HEADER.NumberOfSections + 1)
        self.assertEqual(patched.sections[-1].Name, patcher.SECTION_NAME)
        self.assertEqual(patched.OPTIONAL_HEADER.AddressOfEntryPoint, patched.sections[-1].VirtualAddress)
        self.assertEqual(patched.DIRECTORY_ENTRY_IMPORT[0].dll, b"KERNEL32.dll")
        self.assertEqual([(d.dll, [(i.name, i.address) for i in d.imports]) for d in patched.DIRECTORY_ENTRY_IMPORT],
                         [(d.dll, [(i.name, i.address) for i in d.imports]) for d in original.DIRECTORY_ENTRY_IMPORT])
        section = patched.sections[-1]
        code = section.get_data()[:section.Misc_VirtualSize]
        instructions = list(capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32).disasm(
            code, patcher.IMAGE_BASE + section.VirtualAddress))
        self.assertEqual(sum(item.size for item in instructions), len(code))
        self.assertEqual(instructions[0].mnemonic, "pushfd")
        self.assertEqual(instructions[1].mnemonic, "pushal")
        self.assertEqual(instructions[-2].mnemonic, "popfd")
        self.assertEqual(instructions[-1].mnemonic, "jmp")
        self.assertEqual(instructions[-1].op_str, hex(patcher.IMAGE_BASE + original.OPTIONAL_HEADER.AddressOfEntryPoint))
        boundaries = {item.address for item in instructions}
        for item in instructions[:-1]:
            if item.mnemonic.startswith("j"):
                self.assertIn(int(item.op_str, 16), boundaries)
        calls = [item.op_str for item in instructions if item.mnemonic == "call"]
        filename, library = patcher.client_imports(self.original, patcher.pe_layout(self.original))
        self.assertEqual(calls, [f"dword ptr [{hex(filename)}]", f"dword ptr [{hex(library)}]", "eax"])

    def test_customized_build_accepted_and_wrong_version_rejected(self):
        changed = bytearray(self.original)
        changed[0x1000] ^= 1
        self.assertEqual(patcher.restore_bytes(patcher.patch_bytes(changed)), changed)
        signature = struct.pack("<IIII", 0xFEEF04BD, 0x10000, 0x30003, (5 << 16) | 12340)
        version = changed.index(signature)
        struct.pack_into("<I", changed, version + 12, (5 << 16) | 12341)
        with self.assertRaisesRegex(ValueError, "3.3.5.12340"):
            patcher.patch_bytes(changed)


if __name__ == "__main__":
    unittest.main()
