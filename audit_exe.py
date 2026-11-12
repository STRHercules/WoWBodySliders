"""Read-only, build-pinned Shadowlands inventory; candidates are not live hooks."""

import argparse
import hashlib
import json
from pathlib import Path
import struct

import capstone
import pefile


TARGET_SHA256 = "c5083750b1892cf0c3a029295f3298599558a9b25c6d988c3f107b47f1aff199"
TARGET_VERSION = [9, 2, 7, 45745]
ANCHORS = (
    "UnitGUID", "UnitName", "UnitRace", "CreateFrame", "SetUnit",
    "GetModelFileID", "SetModel", "SetScale", "PlayerModel", "ModelScene",
    "RegisterAddonMessagePrefix",
    "SetCustomRace", "SetCreature", "SetPortraitZoom", "RefreshUnit",
    "SetDisplayInfo", "Undress", "TryOn", "SetAnimation", "GetModelUnitGUID",
)


def occurrences(data, needle):
    offset = data.find(needle)
    while offset != -1:
        yield offset
        offset = data.find(needle, offset + 1)


def file_rva(pe, offset):
    # Reject PE overlays and section padding interpreted as virtual addresses.
    for section in pe.sections:
        delta = offset - section.PointerToRawData
        if 0 <= delta < min(section.SizeOfRawData, section.Misc_VirtualSize):
            return section.VirtualAddress + delta
    return None


def registration_candidates(pe, names=ANCHORS):
    """Find name/function pairs, corroborated by executable code and x64 unwind data.

    Table ownership and function semantics still need disassembly/runtime analysis.
    A missing pair does not mean an API is absent (tables may use another layout).
    """
    data = pe.__data__
    base = pe.OPTIONAL_HEADER.ImageBase
    functions = {entry.struct.BeginAddress: entry.struct.EndAddress
                 for entry in getattr(pe, "DIRECTORY_ENTRY_EXCEPTION", ())}
    disassembler = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    results = {}
    for name in names:
        strings, candidates = [], []
        for found in occurrences(data, b"\0" + name.encode("ascii") + b"\0"):
            string_rva = file_rva(pe, found + 1)
            if string_rva is None:
                continue
            strings.append(string_rva)
            for offset in occurrences(data, struct.pack("<Q", base + string_rva)):
                pair_rva = file_rva(pe, offset)
                end_rva = file_rva(pe, offset + 15)
                if pair_rva is None or pair_rva % 8 or end_rva != pair_rva + 15:
                    continue
                function_rva = struct.unpack_from("<Q", data, offset + 8)[0] - base
                end = functions.get(function_rva)
                section = pe.get_section_by_rva(function_rva) if end else None
                if not section or not section.Characteristics & 0x20000000 or end <= function_rva:
                    continue
                prefix = pe.get_data(function_rva, min(32, end - function_rva))
                instructions = [dict(rva=instruction.address, mnemonic=instruction.mnemonic,
                                     operands=instruction.op_str)
                                for instruction in disassembler.disasm(prefix, function_rva)]
                candidates.append(dict(pair_rva=pair_rva, string_rva=string_rva,
                                       function_rva=function_rva, function_end_rva=end,
                                       prefix_hex=prefix.hex(), prefix_disassembly=instructions,
                                       callable_verified=False))
        results[name] = dict(string_rvas=strings, candidates=candidates)
    return results


def registration_tables(pe, anchors):
    """Group adjacent validated pairs; adjacency is evidence, not a class name."""
    functions = {entry.struct.BeginAddress for entry in getattr(pe, "DIRECTORY_ENTRY_EXCEPTION", ())}
    base = pe.OPTIONAL_HEADER.ImageBase

    def pair(rva):
        section = pe.get_section_by_rva(rva)
        if not section or rva < section.VirtualAddress or rva + 16 > section.VirtualAddress + min(section.SizeOfRawData, section.Misc_VirtualSize):
            return None
        string, function = struct.unpack("<QQ", pe.get_data(rva, 16))
        string, function = string - base, function - base
        string_section = pe.get_section_by_rva(string)
        code_section = pe.get_section_by_rva(function)
        if (not string_section or not code_section or function not in functions
                or not code_section.Characteristics & 0x20000000):
            return None
        name = pe.get_string_at_rva(string, 96)
        if not name or len(name) >= 96 or not (65 <= name[0] <= 90 or 97 <= name[0] <= 122 or name[0] == 95):
            return None
        if not all(65 <= c <= 90 or 97 <= c <= 122 or 48 <= c <= 57 or c == 95 for c in name):
            return None
        return dict(pair_rva=rva, name=name.decode("ascii"), function_rva=function)

    covered, tables = set(), []
    for anchor in anchors.values():
        for candidate in anchor["candidates"]:
            seed = candidate["pair_rva"]
            if seed in covered:
                continue
            start = seed
            for _ in range(128):
                if not pair(start - 16):
                    break
                start -= 16
            entries = []
            for index in range(256):
                entry = pair(start + index * 16)
                if not entry:
                    break
                entries.append(entry)
                covered.add(entry["pair_rva"])
            if entries:
                tables.append(dict(start_rva=start, entries=entries, callable_verified=False,
                                   bounded_scan=True))
    return tables


def audit(data):
    digest = hashlib.sha256(data).hexdigest()
    if digest != TARGET_SHA256:
        raise ValueError("Unsupported executable: expected the supplied 9.2.7.45745 SHA-256")
    pe = pefile.PE(data=data)
    try:
        if pe.FILE_HEADER.Machine != 0x8664 or pe.OPTIONAL_HEADER.Magic != 0x20B:
            raise ValueError("Expected an AMD64 PE32+ executable")
        info = pe.VS_FIXEDFILEINFO[0]
        version = [info.FileVersionMS >> 16, info.FileVersionMS & 0xFFFF,
                   info.FileVersionLS >> 16, info.FileVersionLS & 0xFFFF]
        if version != TARGET_VERSION:
            raise ValueError("Unexpected executable version")
        imports = [dict(dll=entry.dll.decode("ascii"), symbols=[
            dict(name=symbol.name.decode("ascii") if symbol.name else None,
                 ordinal=symbol.ordinal, iat_rva=symbol.address - pe.OPTIONAL_HEADER.ImageBase)
            for symbol in entry.imports])
            for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", ())]
        anchors = registration_candidates(pe)
        return dict(
            schema=2, stage="static reconnaissance; runtime backend not implemented",
            sha256=digest, size=len(data), version=version, machine="AMD64", pe_format="PE32+",
            preferred_image_base=pe.OPTIONAL_HEADER.ImageBase,
            aslr=bool(pe.OPTIONAL_HEADER.DllCharacteristics & 0x40),
            entry_rva=pe.OPTIONAL_HEADER.AddressOfEntryPoint,
            sections=[dict(name=section.Name.rstrip(b"\0").decode("ascii"),
                           rva=section.VirtualAddress, virtual_size=section.Misc_VirtualSize,
                           raw_offset=section.PointerToRawData, raw_size=section.SizeOfRawData,
                           entropy=section.get_entropy(),
                           executable=bool(section.Characteristics & 0x20000000))
                      for section in pe.sections],
            normal_imports=imports,
            runtime_function_count=len(getattr(pe, "DIRECTORY_ENTRY_EXCEPTION", ())),
            tls_callback_rvas=tls_callbacks(pe),
            anchors=anchors, api_tables=registration_tables(pe, anchors),
            limitations=[
                "Name/function pairs are candidates; table owner and ABI are unverified.",
                "The target code section appears transformed on disk; disassembly prefixes are raw bytes, not validated instructions.",
                "All reported code addresses are RVAs; add the actual module base at runtime.",
                "Normal imports do not describe dynamic API resolution or the full loader lifecycle.",
                "No skeleton, vertex layout, rendering hook or Lua callback path is validated.",
                "No target execution, injection, executable patching or game-data inspection occurred.",
            ],
        )
    finally:
        pe.close()


def tls_callbacks(pe):
    directory = getattr(pe, "DIRECTORY_ENTRY_TLS", None)
    if directory is None:
        return []
    base = pe.OPTIONAL_HEADER.ImageBase
    array = directory.struct.AddressOfCallBacks - base
    result = []
    for index in range(32):
        rva = array + index * 8
        section = pe.get_section_by_rva(rva)
        if not section or rva + 8 > section.VirtualAddress + min(section.SizeOfRawData, section.Misc_VirtualSize):
            raise ValueError("TLS callback array outside file-backed sections")
        address = struct.unpack("<Q", pe.get_data(rva, 8))[0]
        if not address:
            return result
        if not base <= address < base + pe.OPTIONAL_HEADER.SizeOfImage:
            raise ValueError("TLS callback outside image")
        result.append(address - base)
    raise ValueError("Unterminated TLS callback array")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("--output", type=Path, help="Create a new JSON report; never overwrite a file")
    args = parser.parse_args()
    try:
        result = json.dumps(audit(args.executable.read_bytes()), indent=2) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(result)
        else:
            print(result, end="")
    except (OSError, ValueError, pefile.PEFormatError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
