from pathlib import Path
import hashlib
import struct
import unittest

try:
    import unicorn as u
except ImportError:
    u = None

if u:
    from unicorn import x86_const as x
    from shadowlands import probe_startup as probe


@unittest.skipUnless(u, "Optional offline probe requires shadowlands/requirements-analysis.txt")
class ProbeTests(unittest.TestCase):
    def test_exception_context_round_trip(self):
        uc = u.Uc(u.UC_ARCH_X86, u.UC_MODE_64)
        uc.mem_map(0x100000, 4096)
        values = {}
        for index, (register, _) in enumerate(probe.REGISTERS):
            values[register] = 0x12340000 + index * 16
            uc.reg_write(register, values[register])
        uc.reg_write(x.UC_X86_REG_EFLAGS, 0x302)
        probe.save_context(uc, 0x100000, 0x14000CA4C)
        for register, _ in probe.REGISTERS:
            uc.reg_write(register, 0)
        uc.reg_write(x.UC_X86_REG_EFLAGS, 0x202)
        probe.restore_context(uc, 0x100000)
        for register, _ in probe.REGISTERS:
            self.assertEqual(uc.reg_read(register), 0x14000CA4C if register == x.UC_X86_REG_RIP else values[register])
        self.assertEqual(uc.reg_read(x.UC_X86_REG_EFLAGS), 0x302)
        self.assertEqual(struct.unpack("<I", uc.mem_read(0x100030, 4))[0], 0x100003)

    def test_unknown_executable_rejected_before_environment_loading(self):
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            probe.probe(b"MZ", Path("not-a-system-directory"))

    def test_supplied_startup_stops_at_first_protection_fault(self):
        path = Path(__file__).resolve().parents[1] / "Wow-Shadowlands.exe"
        system = Path("C:/Windows/System32")
        if not path.is_file() or not (system / "kernel32.dll").is_file():
            self.skipTest("Requires supplied executable and Windows x64 system export metadata")
        data = path.read_bytes()
        result = probe.probe(data, system, max_exceptions=0)
        self.assertEqual(result["stop_reason"], "exception limit")
        self.assertEqual(result["initial_callback_rvas"], [0x3D20, 0x246EB0, 0x28940F8])
        self.assertEqual(result["final_callback_rvas"], [0x2B6B60, 0x9D30, 0x2B6A60, 0x246EB0, 0x28940F8])
        self.assertEqual(result["handler_rva"], 0x2B150)
        self.assertEqual(result["stop_rva"], 0xCA4D)
        self.assertEqual([event["name"] for event in result["api_events"]],
                         ["VirtualProtect", "VirtualProtect", "RtlAddVectoredExceptionHandler"])
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), result["sha256"])


if __name__ == "__main__":
    unittest.main()
