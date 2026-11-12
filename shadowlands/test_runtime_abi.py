import hashlib
from pathlib import Path
import re
import struct
import unittest

import capstone
import pefile


class EpsilonAbiTests(unittest.TestCase):
    def test_lua_slots_match_actual_epsilon_initialization(self):
        path = Path("D:/Epsilon/Epsilon/_retail_/EpsilonAddon.dll")
        if not path.is_file(): self.skipTest("Requires pinned EpsilonAddon.dll")
        data = path.read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), "b3fba2a4059212bebc11c9bcc104b1b008c236cf156ab89014386748cd299fb8")
        pe = pefile.PE(data=data, fast_load=True)
        try:
            cs = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); cs.detail = True
            initialized, game_rva = {}, None
            for instruction in cs.disasm(pe.get_data(0x29740, 0x350), 0x29740):
                if instruction.mnemonic != "mov" or len(instruction.operands) != 2: continue
                destination, source = instruction.operands
                if (destination.type == capstone.CS_OP_REG and destination.reg == capstone.x86.X86_REG_RCX
                        and source.type == capstone.CS_OP_MEM and source.mem.base == capstone.x86.X86_REG_RIP):
                    slot = instruction.address + instruction.size + source.mem.disp
                    game_rva = struct.unpack("<Q", pe.get_data(slot, 8))[0]
                elif (destination.type == capstone.CS_OP_MEM and destination.mem.base == capstone.x86.X86_REG_RIP
                        and source.type == capstone.CS_OP_REG and source.reg == capstone.x86.X86_REG_RCX):
                    slot = instruction.address + instruction.size + destination.mem.disp
                    initialized[slot] = game_rva
            source = (Path(__file__).resolve().parent / "RuntimeBridge.h").read_text()
            pairs = [(int(a, 16), int(b, 16)) for a, b in re.findall(r"\{(0x2FA[0-9A-F]+), (0x[0-9A-F]+)\}", source)]
            self.assertEqual(len(pairs), 8)
            for slot, target in pairs:
                with self.subTest(slot=hex(slot)): self.assertEqual(initialized[slot], target)
            self.assertEqual(initialized[0x2FA590], 0x2C7CD0)
            self.assertNotEqual(initialized[0x2FA5A0], 0x2C7CD0)
            self.assertEqual(initialized[0x2FA520], 0x2C63E0)
            bindings = {"Top": 0x2C63E0, "SetTop": 0x2C7840, "Type": 0x2C7CD0,
                        "Number": 0x2C7BC0, "PushNumber": 0x2C6DE0, "PushBool": 0x2C6B30,
                        "PushString": 0x2C6E00, "SetTable": 0x2C71A0, "Pcall": 0x2C6A60}
            for name, target in bindings.items():
                with self.subTest(binding=name):
                    self.assertRegex(source, rf"auto {name} = .*?\(0x{target:X}\)")
        finally:
            pe.close()


if __name__ == "__main__": unittest.main()
