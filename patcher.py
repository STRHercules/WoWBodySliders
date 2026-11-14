"""Reversible BodySlider loader patch for WoW 3.3.5a build 12340 executables.

No third-party Python packages are required. The source file is never modified.
The DLL contract is a zero-argument cdecl initializer exported at ordinal 1.
"""

import argparse
import base64
import hashlib
import json
from pathlib import Path
import struct


STOCK_SHA256 = "aa63a5750d60ef16746c686b3d5e26876d98953eab08b1c026cd0faf78e88cb8"
MARKER = b"BodySliderPatch1\0"
SECTION_NAME = b".bslide\0"
IMAGE_BASE = 0x400000
GET_MODULE_FILENAME_A = 0x9DF1A0
LOAD_LIBRARY_A = 0x9DF248


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def align(value, alignment):
    return (value + alignment - 1) // alignment * alignment


def pe_layout(data):
    """Read and validate the PE fields needed by the loader patch."""
    if len(data) < 64 or data[:2] != b"MZ":
        raise ValueError("Not a DOS/PE executable")
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if pe + 24 > len(data) or data[pe:pe + 4] != b"PE\0\0":
        raise ValueError("Missing or truncated PE header")
    machine, count = struct.unpack_from("<HH", data, pe + 4)
    optional_size = struct.unpack_from("<H", data, pe + 20)[0]
    optional = pe + 24
    sections = optional + optional_size
    if machine != 0x14C or optional_size < 224 or sections + count * 40 > len(data):
        raise ValueError("Expected a complete x86 PE32 executable")
    if struct.unpack_from("<H", data, optional)[0] != 0x10B or count == 0:
        raise ValueError("Expected PE32 section headers")
    image_base = struct.unpack_from("<I", data, optional + 28)[0]
    dll_flags = struct.unpack_from("<H", data, optional + 70)[0]
    if image_base != IMAGE_BASE or dll_flags & 0x40:
        raise ValueError("Expected image base 0x400000 with ASLR disabled")
    section_alignment, file_alignment = struct.unpack_from("<II", data, optional + 32)
    headers_size = struct.unpack_from("<I", data, optional + 60)[0]
    if (section_alignment != 0x1000 or file_alignment != 0x200
            or headers_size > len(data) or sections + count * 40 > headers_size):
        raise ValueError("Unexpected PE alignment or insufficient section-header space")
    next_rva = 0
    for index in range(count):
        section = sections + index * 40
        virtual_size, virtual_address, raw_size, raw_address = struct.unpack_from("<IIII", data, section + 8)
        if raw_address + raw_size > len(data):
            raise ValueError("Truncated section")
        next_rva = max(next_rva, virtual_address + max(virtual_size, raw_size))
    return dict(pe=pe, optional=optional, count=count, sections=sections,
                headers_size=headers_size, file_alignment=file_alignment,
                section_alignment=section_alignment,
                next_rva=align(next_rva, section_alignment))


def client_imports(data, layout):
    """Validate the version resource and resolve the loader's two IAT slots."""
    def offset(rva, size):
        for index in range(layout["count"]):
            section = layout["sections"] + index * 40
            _, address, length, raw = struct.unpack_from("<IIII", data, section + 8)
            if address <= rva and rva + size <= address + length:
                return raw + rva - address
        raise ValueError("Invalid PE data RVA")

    optional = layout["optional"]
    resource_rva, resource_size = struct.unpack_from("<II", data, optional + 112)
    resource = offset(resource_rva, resource_size)

    def resource_entry(relative, wanted=None):
        if relative + 16 > resource_size:
            raise ValueError("Invalid version resource directory")
        named, ids = struct.unpack_from("<HH", data, resource + relative + 12)
        for index in range(named + ids):
            entry = relative + 16 + index * 8
            if entry + 8 > resource_size:
                raise ValueError("Truncated version resource directory")
            name, target = struct.unpack_from("<II", data, resource + entry)
            if wanted is None or name == wanted:
                return target
        raise ValueError("Missing executable version resource")

    target = resource_entry(0, 16)  # RT_VERSION / name / language
    for _ in range(2):
        if not target & 0x80000000:
            raise ValueError("Invalid version resource tree")
        target = resource_entry(target & 0x7fffffff)
    if target & 0x80000000 or target + 16 > resource_size:
        raise ValueError("Invalid version resource data")
    rva, size = struct.unpack_from("<II", data, resource + target)
    start = offset(rva, size)
    version = data[start:start + size]
    key = "VS_VERSION_INFO\0".encode("utf-16le")
    fixed = align(6 + len(key), 4)
    if (version[6:6 + len(key)] != key or len(version) < fixed + 52
            or struct.unpack_from("<IIII", version, fixed) !=
            (0xFEEF04BD, 0x10000, 0x30003, (5 << 16) | 12340)):
        raise ValueError("Expected WoW version 3.3.5.12340")

    imports_rva, imports_size = struct.unpack_from("<II", data, optional + 104)
    imports = offset(imports_rva, imports_size)
    found = {}
    for descriptor in range(imports, imports + imports_size - 19, 20):
        lookup, _, _, name, iat = struct.unpack_from("<IIIII", data, descriptor)
        if not name:
            break
        name_offset = offset(name, 13)
        if data[name_offset:name_offset + 13].lower() != b"kernel32.dll\0":
            continue
        for index in range(len(data) // 4):
            thunk = struct.unpack_from("<I", data, offset((lookup or iat) + index * 4, 4))[0]
            if not thunk:
                break
            if thunk & 0x80000000:
                continue
            for function in (b"GetModuleFileNameA", b"LoadLibraryA"):
                name_offset = offset(thunk + 2, len(function) + 1)
                if data[name_offset:name_offset + len(function) + 1] == function + b"\0":
                    offset(iat + index * 4, 4)
                    found[function] = IMAGE_BASE + iat + index * 4
    if len(found) != 2:
        raise ValueError("Missing required KERNEL32 loader imports")
    return found[b"GetModuleFileNameA"], found[b"LoadLibraryA"]


def bootstrap(section_rva, entry_rva, get_filename=GET_MODULE_FILENAME_A, load_library=LOAD_LIBRARY_A):
    """Preserve entry state, load beside the EXE, initialize, resume stock entry."""
    code = bytearray()
    labels = {}
    jumps = []

    def emit(hex_bytes):
        code.extend(bytes.fromhex(hex_bytes))

    def jump(opcode, label):
        emit(opcode)
        jumps.append((len(code), label))
        code.extend(b"\0" * 4)

    def label(name):
        labels[name] = len(code)

    emit("9c 60 81 ec 00 04 00 00 89 e7")  # pushfd; pushad; path[1024]
    emit("68 00 04 00 00 57 6a 00 ff 15")
    code.extend(struct.pack("<I", get_filename))
    emit("85 c0")
    jump("0f 84", "done")
    emit("3d f1 03 00 00")  # reject zero/truncated path; reserve 15 bytes
    jump("0f 87", "done")
    emit("8d 34 07")  # esi = path + length
    label("slash")
    emit("39 fe")
    jump("0f 86", "done")
    emit("4e 80 3e 5c")
    jump("0f 84", "basename")
    emit("80 3e 2f")
    jump("0f 85", "slash")
    label("basename")
    emit("46")
    for offset in range(0, 12, 4):
        emit("c7 46")
        code.append(offset)
        code.extend(b"BodySlider.dll\0"[offset:offset + 4])
    emit("66 c7 46 0c 6c 6c c6 46 0e 00")
    emit("57 ff 15")
    code.extend(struct.pack("<I", load_library))
    emit("85 c0")
    jump("0f 84", "done")
    emit("89 c3 8b 43 3c 8b 54 03 78 8b 4c 03 7c 85 d2")
    jump("0f 84", "done")
    emit("8d 2c 13 be 01 00 00 00 2b 75 10")  # ordinal index = 1 - export.Base
    emit("3b 75 14")
    jump("0f 83", "done")
    emit("8b 45 1c 01 d8 8b 04 b0 85 c0")
    jump("0f 84", "done")
    emit("39 d0")
    jump("0f 82", "initialize")
    emit("01 d1 39 c8")  # do not call a forwarded export string
    jump("0f 82", "done")
    label("initialize")
    emit("01 d8 ff d0")  # initializer runs after LoadLibraryA released loader lock
    label("done")
    emit("81 c4 00 04 00 00 61 9d e9")
    code.extend(struct.pack("<i", entry_rva - (section_rva + len(code) + 4)))
    for offset, target in jumps:
        struct.pack_into("<i", code, offset, labels[target] - (offset + 4))
    return bytes(code)


def pe_checksum(data, checksum_offset):
    total = 0
    for offset in range(0, len(data), 2):
        word = 0 if checksum_offset <= offset < checksum_offset + 4 else int.from_bytes(data[offset:offset + 2], "little")
        total += word
        total = (total & 0xFFFF) + (total >> 16)
    total = (total & 0xFFFF) + (total >> 16)
    return total + len(data)


def patch_bytes(original):
    if original.endswith(MARKER):
        raise ValueError("Executable is already patched")
    layout = pe_layout(original)
    if layout["sections"] + (layout["count"] + 1) * 40 > layout["headers_size"]:
        raise ValueError("Insufficient section-header space")
    if any(original[layout["sections"] + i * 40:layout["sections"] + i * 40 + 8] == SECTION_NAME
           for i in range(layout["count"])):
        raise ValueError("Executable already contains a BodySlider section")
    optional = layout["optional"]
    entry = struct.unpack_from("<I", original, optional + 16)[0]
    stub = bootstrap(layout["next_rva"], entry, *client_imports(original, layout))
    raw_address = align(len(original), layout["file_alignment"])
    raw_size = align(len(stub), layout["file_alignment"])
    output = bytearray(original)
    output.extend(b"\0" * (raw_address + raw_size - len(output)))
    output[raw_address:raw_address + len(stub)] = stub
    new_section = layout["sections"] + layout["count"] * 40
    struct.pack_into("<8sIIIIIIHHI", output, new_section, SECTION_NAME, len(stub),
                     layout["next_rva"], raw_size, raw_address, 0, 0, 0, 0, 0x60000020)
    struct.pack_into("<H", output, layout["pe"] + 6, layout["count"] + 1)
    struct.pack_into("<I", output, optional + 4, struct.unpack_from("<I", original, optional + 4)[0] + raw_size)
    struct.pack_into("<I", output, optional + 16, layout["next_rva"])
    struct.pack_into("<I", output, optional + 56,
                     align(layout["next_rva"] + len(stub), layout["section_alignment"]))
    # Modifying a signed executable invalidates its signature; retain its bytes for exact restoration.
    output[optional + 128:optional + 136] = b"\0" * 8
    struct.pack_into("<I", output, optional + 64, 0)
    metadata = dict(version=1, original_size=len(original), original_sha256=sha256(original),
                    original_headers=base64.b64encode(original[:layout["headers_size"]]).decode("ascii"),
                    body_sha256=sha256(output))
    metadata_bytes = json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode("ascii")
    output.extend(metadata_bytes + struct.pack("<I", len(metadata_bytes)) + MARKER)
    struct.pack_into("<I", output, optional + 64, pe_checksum(output, optional + 64))
    return bytes(output)


def restore_bytes(patched):
    if not patched.endswith(MARKER) or len(patched) < len(MARKER) + 4:
        raise ValueError("Not a BodySlider-patched executable")
    size_offset = len(patched) - len(MARKER) - 4
    metadata_size = struct.unpack_from("<I", patched, size_offset)[0]
    if metadata_size > 16384 or metadata_size > size_offset:
        raise ValueError("Invalid patch metadata length")
    body = bytearray(patched[:size_offset - metadata_size])
    try:
        metadata = json.loads(patched[size_offset - metadata_size:size_offset])
        layout = pe_layout(body)
        struct.pack_into("<I", body, layout["optional"] + 64, 0)
        if metadata["version"] != 1 or sha256(body) != metadata["body_sha256"]:
            raise ValueError("Patched executable has changed; refusing restoration")
        headers = base64.b64decode(metadata["original_headers"], validate=True)
        original_size = metadata["original_size"]
        if len(headers) != layout["headers_size"] or not len(headers) <= original_size <= len(body):
            raise ValueError("Invalid restoration bounds")
        original = headers + bytes(body[len(headers):original_size])
        if sha256(original) != metadata["original_sha256"]:
            raise ValueError("Restored executable does not match the original digest")
    except (KeyError, TypeError, UnicodeError, json.JSONDecodeError, struct.error) as exc:
        raise ValueError("Invalid patch metadata") from exc
    return original


def write_copy(source, destination, restore=False):
    source = Path(source).resolve()
    destination = Path(destination).resolve()
    if source == destination:
        raise ValueError("Input and output must be different files")
    if destination.exists():
        raise ValueError("Output already exists; refusing to overwrite it")
    result = (restore_bytes if restore else patch_bytes)(source.read_bytes())
    # Exclusive creation also protects against a file appearing after the existence check.
    with destination.open("xb") as stream:
        stream.write(result)
    return sha256(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path, help="new output file; existing files are never replaced")
    parser.add_argument("--restore", action="store_true", help="restore a patched copy byte-for-byte")
    args = parser.parse_args()
    try:
        digest = write_copy(args.source, args.output, args.restore)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"BodySlider: {exc}\n")
    print(f"Created {args.output}\nSHA-256: {digest}")


if __name__ == "__main__":
    main()
