import struct
import unittest
from shadowlands.tls_loader_data import CODE

try:
    import unicorn as u
except ImportError:
    u = None
if u:
    from unicorn import x86_const as x


@unittest.skipUnless(u, "Optional Unicorn required")
class TlsLoaderTests(unittest.TestCase):
    def check(self, base, available):
        uc = u.Uc(u.UC_ARCH_X86, u.UC_MODE_64)
        stack, env, kernel = 0x10000000, 0x70000000, 0x200000000
        for address in (base, stack, env, kernel): uc.mem_map(address, 0x10000)
        uc.mem_write(base + 0x2000, CODE)
        def q(address, value): uc.mem_write(address, struct.pack("<Q", value))
        q(env + 0x60, env + 0x1000); q(env + 0x1018, env + 0x2000)
        head, link = env + 0x2020, env + 0x3010
        q(head, link if available else head); q(link, head); q(link + 0x20, kernel)
        uc.mem_write(link + 0x48, struct.pack("<H", 24)); q(link + 0x50, env + 0x4000)
        uc.mem_write(env + 0x4000, "KERNEL32.DLL".encode("utf-16-le"))
        uc.mem_write(kernel + 0x3C, struct.pack("<I", 0x80))
        uc.mem_write(kernel + 0x108, struct.pack("<II", 0x1000, 0x100))
        uc.mem_write(kernel + 0x1018, struct.pack("<IIII", 1, 0x1200, 0x1210, 0x1220))
        uc.mem_write(kernel + 0x1200, struct.pack("<I", 0x3000))
        uc.mem_write(kernel + 0x1210, struct.pack("<I", 0x1300))
        uc.mem_write(kernel + 0x1300, b"LoadLibraryExW\0")
        uc.reg_write(x.UC_X86_REG_GS_BASE, env)
        registers = (x.UC_X86_REG_RAX, x.UC_X86_REG_RCX, x.UC_X86_REG_RDX, x.UC_X86_REG_RBX,
                     x.UC_X86_REG_RSI, x.UC_X86_REG_RDI, x.UC_X86_REG_R8, x.UC_X86_REG_R9,
                     x.UC_X86_REG_R10, x.UC_X86_REG_R11, x.UC_X86_REG_R12, x.UC_X86_REG_R13,
                     x.UC_X86_REG_R14, x.UC_X86_REG_R15)
        expected = {reg: 0x12340000 + i * 16 for i, reg in enumerate(registers)}
        for reg, value in expected.items(): uc.reg_write(reg, value)
        rsp = stack + 0xF000
        uc.reg_write(x.UC_X86_REG_RSP, rsp); uc.reg_write(x.UC_X86_REG_RBP, 0x1234)
        uc.reg_write(x.UC_X86_REG_EFLAGS, 0x202)
        q(rsp + 0x170, 0x5678); q(rsp + 0x178, base + 0x1000)
        for i in range(6): uc.reg_write(x.UC_X86_REG_XMM0 + i, (i + 1) * 0x123456789ABCDEF)
        calls = []
        def api(uc, address, size, user):
            sp = uc.reg_read(x.UC_X86_REG_RSP)
            self.assertEqual(sp % 16, 8)
            self.assertEqual(uc.reg_read(x.UC_X86_REG_R8), 0xA00)
            self.assertEqual(bytes(uc.mem_read(uc.reg_read(x.UC_X86_REG_RCX), 52)).decode("utf-16-le").split("\0")[0], "BodySliderShadowlands.dll")
            calls.append(address)
            uc.reg_write(x.UC_X86_REG_RAX, 0) # DLL missing: preserve ordinary client startup.
            uc.reg_write(x.UC_X86_REG_XMM0, 0)
            uc.reg_write(x.UC_X86_REG_RIP, struct.unpack("<Q", uc.mem_read(sp, 8))[0])
            uc.reg_write(x.UC_X86_REG_RSP, sp + 8)
        uc.hook_add(u.UC_HOOK_CODE, api, begin=kernel + 0x3000, end=kernel + 0x3000)
        uc.emu_start(base + 0x2000, base + 0x1000, count=10000)
        for reg, value in expected.items(): self.assertEqual(uc.reg_read(reg), value)
        self.assertEqual(uc.reg_read(x.UC_X86_REG_RSP), rsp + 0x180)
        self.assertEqual(uc.reg_read(x.UC_X86_REG_RBP), 0x5678)
        for i in range(6): self.assertEqual(uc.reg_read(x.UC_X86_REG_XMM0 + i), (i + 1) * 0x123456789ABCDEF)
        self.assertEqual(len(calls), int(available))

    def test_aslr_epilogue_and_missing_dll_fallback(self):
        self.check(0x140000000, True)
        self.check(0x7FF700000000, True)
        self.check(0x140000000, False)


if __name__ == "__main__": unittest.main()
