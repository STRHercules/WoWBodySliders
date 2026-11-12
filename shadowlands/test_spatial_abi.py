from pathlib import Path
import struct
import unittest
import capstone


class SpatialAbiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / "build/shadowlands/initialized-text-late.bin"
        if not path.is_file(): raise unittest.SkipTest("Requires initialized-code capture")
        cls.code = path.read_bytes()

    def test_unit_call_and_spatial_setter(self):
        code = self.code
        at = 0x183F53A
        self.assertEqual(code[at-0x1000:at-0x1000+5], bytes.fromhex("e8916eb4ff"))
        self.assertEqual(at+5+struct.unpack_from("<i",code,at-0x1000+1)[0],0x13863D0)
        self.assertEqual(code[0x13863D0-0x1000:0x13863D0-0x1000+5], bytes.fromhex("e9abb1e8ff"))
        self.assertEqual(0x13863D5+struct.unpack_from("<i",code,0x13863D1-0x1000)[0],0x1211580)
        cs=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64)
        instructions=list(cs.disasm_lite(code[0x1211607-0x1000:0x121163A-0x1000],0x1211607))
        stores=[operand for _,_,name,operand in instructions if name=="movups" and operand.startswith("xmmword ptr [rdi")]
        self.assertEqual(stores,["xmmword ptr [rdi + 0x100], xmm0","xmmword ptr [rdi + 0x110], xmm1",
                                 "xmmword ptr [rdi + 0x120], xmm0","xmmword ptr [rdi + 0x130], xmm1"])

    def test_alpha_setter_is_not_used_as_size(self):
        code=self.code;at=0x29B340F
        self.assertEqual(code[at-0x1000],0xE8)
        self.assertEqual(at+5+struct.unpack_from("<i",code,at-0x1000+1)[0],0x1385B60)
        source=(Path(__file__).resolve().parent/"RuntimeBridge.h").read_text()
        self.assertNotIn("0x1385B60",source)
        self.assertNotIn("0x328",source)

    def test_allowlisted_source_getters_are_plain_float_reads(self):
        for rva, offset in ((0x1760820,0x3E0),(0x1864690,0x3D0),(0x18D2FC0,0xD8),(0x19D3A90,0xF8)):
            with self.subTest(rva=hex(rva)):
                expected=bytes.fromhex("f30f1081")+struct.pack("<I",offset)+b"\xc3"
                self.assertEqual(self.code[rva-0x1000:rva-0x1000+9],expected)


if __name__=="__main__":unittest.main()
