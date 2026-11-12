"""Execute captured Lua machine-code primitives against synthetic stack state."""
from pathlib import Path
import struct
import unittest

try:
    import unicorn as u
except ImportError:
    u = None
if u:
    from unicorn import x86_const as x


@unittest.skipUnless(u, "Requires optional Unicorn")
class LuaMachineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / "build/shadowlands/initialized-text-late.bin"
        if not path.is_file(): raise unittest.SkipTest("Requires retained initialized-code capture")
        cls.code = path.read_bytes()

    def test_real_gettop_settop_and_scalar_pushes(self):
        uc = u.Uc(u.UC_ARCH_X86, u.UC_MODE_64)
        base, lua, stack, cpu, stop = 0x140000000, 0x20000000, 0x20001000, 0x30000000, 0x40000000
        uc.mem_map(base, 0x4000000); uc.mem_write(base + 0x1000, self.code)
        uc.mem_map(lua, 0x10000); uc.mem_map(cpu, 0x10000); uc.mem_map(stop, 4096)
        def q(address, value): uc.mem_write(address, struct.pack("<Q", value))
        def read(address): return struct.unpack("<Q", uc.mem_read(address, 8))[0]
        q(lua + 0x28, stack); q(lua + 0x30, stack)
        def call(rva, second=0, double=None):
            rsp = cpu + 0xF008; q(rsp, stop)
            uc.reg_write(x.UC_X86_REG_RSP, rsp); uc.reg_write(x.UC_X86_REG_RCX, lua)
            uc.reg_write(x.UC_X86_REG_RDX, second & ((1 << 64) - 1))
            if double is not None: uc.reg_write(x.UC_X86_REG_XMM1, struct.unpack("<Q", struct.pack("<d", double))[0])
            uc.emu_start(base + rva, stop, count=1000)
            self.assertEqual(uc.reg_read(x.UC_X86_REG_RIP), stop)
            return uc.reg_read(x.UC_X86_REG_RAX)
        self.assertEqual(call(0x2C63E0), 0)
        call(0x2C6DE0, double=1.25)
        self.assertEqual(read(lua + 0x28), stack + 24)
        self.assertEqual(struct.unpack("<d", uc.mem_read(stack, 8))[0], 1.25)
        self.assertEqual(struct.unpack("<I", uc.mem_read(stack + 8, 4))[0], 3)
        call(0x2C6B30, 1)
        self.assertEqual(read(lua + 0x28), stack + 48)
        self.assertEqual(struct.unpack("<II", uc.mem_read(stack + 24, 8))[0], 1)
        self.assertEqual(call(0x2C63E0), 2)
        call(0x2C7840, -2); self.assertEqual(call(0x2C63E0), 1)
        call(0x2C7840, 0); self.assertEqual(call(0x2C63E0), 0)
        call(0x2C7840, 3); self.assertEqual(call(0x2C63E0), 3)
        for index in range(3): self.assertEqual(struct.unpack("<I", uc.mem_read(stack + index * 24 + 8, 4))[0], 0)


if __name__ == "__main__": unittest.main()
