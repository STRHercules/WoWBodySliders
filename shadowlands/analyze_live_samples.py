"""Summarize DLL code captures without treating unwind ranges as full functions."""
import argparse
import hashlib
import json
from pathlib import Path

import capstone


def summarize(data, rva):
    cs = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    cs.detail = True
    instructions = list(cs.disasm(data, rva))
    return dict(size=len(data), sha256=hashlib.sha256(data).hexdigest(), prefix_hex=data[:16].hex(),
                decoded_bytes=sum(i.size for i in instructions),
                direct_calls=[dict(site_rva=i.address, target_rva=i.operands[0].imm)
                              for i in instructions if i.mnemonic == "call" and i.operands
                              and i.operands[0].type == capstone.CS_OP_IMM],
                instruction_prefix=[dict(rva=i.address, mnemonic=i.mnemonic, operands=i.op_str)
                                    for i in instructions[:32]])


def analyze(directory, capture_prefix, second):
    root = Path(__file__).resolve().parent
    audit = json.loads((root / "exe-audit.json").read_text())
    functions = []
    for name in ("UnitGUID", "UnitName", "CreateFrame", "SetUnit", "SetModel", "GetModelFileID", "SetCustomRace"):
        for candidate in audit["anchors"][name]["candidates"]:
            rva = candidate["function_rva"]
            source = directory / f"{capture_prefix}-{second:02d}s-{rva:08X}.bin"
            data = source.read_bytes()
            if len(data) != candidate["function_end_rva"] - rva:
                raise ValueError("Incomplete code capture: " + str(source))
            functions.append(dict(name=name, rva=rva, source=source.name,
                                  differs_from_disk=data[:16].hex() != candidate["prefix_hex"][:32],
                                  **summarize(data, rva)))
    return dict(schema=1, executable_sha256=audit["sha256"], capture_prefix=capture_prefix,
                second=second, functions=functions,
                limitations=["Samples are individual unwind regions, not necessarily complete functions.",
                             "Linear disassembly can include unreachable code/data; call edges need tracing.",
                             "Observed machine code does not validate callback ABI or deformation hooks."])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("capture_prefix")
    parser.add_argument("--second", type=int, default=60)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = analyze(args.directory, args.capture_prefix, args.second)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
