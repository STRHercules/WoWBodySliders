"""Build-pinned, reversible direct EXE patch. Always creates a new output file."""
import argparse
import base64
import json
from pathlib import Path
import struct

import pefile
from patcher import align, sha256
from .audit_exe import TARGET_SHA256
from .tls_loader_data import CODE

SITE_RVA = 0x4DBF
ORIGINAL = bytes.fromhex("4881c4700100005dc3")
MARKER = b"BodySliderShadowlandsTLS1\0"


def patch_bytes(data):
    if sha256(data) != TARGET_SHA256:
        raise ValueError("Unsupported source SHA-256; expected supplied 9.2.7.45745")
    pe = pefile.PE(data=data, fast_load=True)
    try:
        optional = pe.OPTIONAL_HEADER.get_file_offset()
        header = pe.sections[-1].get_file_offset() + 40
        if header + 40 > pe.OPTIONAL_HEADER.SizeOfHeaders:
            raise ValueError("No room for loader section header")
        site = pe.get_offset_from_rva(SITE_RVA)
        if data[site:site + len(ORIGINAL)] != ORIGINAL:
            raise ValueError("TLS epilogue differs from the verified build")
        rva = align(max(s.VirtualAddress + max(s.Misc_VirtualSize, s.SizeOfRawData)
                        for s in pe.sections), pe.OPTIONAL_HEADER.SectionAlignment)
        raw = align(len(data), pe.OPTIONAL_HEADER.FileAlignment)
        raw_size = align(len(CODE), pe.OPTIONAL_HEADER.FileAlignment)
        output = bytearray(data)
        output.extend(bytes(raw + raw_size - len(output)))
        output[raw:raw + len(CODE)] = CODE
        output[site:site + len(ORIGINAL)] = b"\xE9" + struct.pack("<i", rva - SITE_RVA - 5) + bytes([0x90]) * 4
        struct.pack_into("<8sIIIIIIHHI", output, header, b".bstls\0\0", len(CODE), rva,
                         raw_size, raw, 0, 0, 0, 0, 0x60000020)
        struct.pack_into("<H", output, pe.FILE_HEADER.get_field_absolute_offset("NumberOfSections"), len(pe.sections) + 1)
        struct.pack_into("<I", output, optional + 4, pe.OPTIONAL_HEADER.SizeOfCode + raw_size)
        struct.pack_into("<I", output, optional + 56, align(rva + len(CODE), pe.OPTIONAL_HEADER.SectionAlignment))
        struct.pack_into("<I", output, optional + 64, 0)
        metadata = dict(version=1, original_size=len(data), site_offset=site,
                        headers=base64.b64encode(data[:pe.OPTIONAL_HEADER.SizeOfHeaders]).decode("ascii"),
                        body_sha256=sha256(output))
        encoded = json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode("ascii")
        output.extend(encoded + struct.pack("<I", len(encoded)) + MARKER)
        check = pefile.PE(data=bytes(output), fast_load=True)
        try:
            struct.pack_into("<I", output, optional + 64, check.generate_checksum())
        finally:
            check.close()
        return bytes(output)
    finally:
        pe.close()


def restore_bytes(data):
    if not data.endswith(MARKER) or len(data) < len(MARKER) + 4:
        raise ValueError("Not a Shadowlands TLS patched executable")
    end = len(data) - len(MARKER) - 4
    size = struct.unpack_from("<I", data, end)[0]
    if not 0 < size <= min(end, 16384):
        raise ValueError("Invalid restoration metadata bounds")
    try:
        metadata = json.loads(data[end - size:end])
        body = bytearray(data[:end - size])
        pe = pefile.PE(data=body, fast_load=True)
        try:
            struct.pack_into("<I", body, pe.OPTIONAL_HEADER.get_file_offset() + 64, 0)
            headers_size = pe.OPTIONAL_HEADER.SizeOfHeaders
            site = pe.get_offset_from_rva(SITE_RVA)
        finally:
            pe.close()
        if metadata["version"] != 1 or sha256(body) != metadata["body_sha256"]:
            raise ValueError("Patched executable changed; refusing restoration")
        headers = base64.b64decode(metadata["headers"], validate=True)
        original_size = metadata["original_size"]
        if (len(headers) != headers_size or not len(headers) <= original_size <= len(body)
                or metadata["site_offset"] != site or site + len(ORIGINAL) > original_size):
            raise ValueError("Invalid restoration bounds")
        body[site:site + len(ORIGINAL)] = ORIGINAL
        original = headers + bytes(body[len(headers):original_size])
        if sha256(original) != TARGET_SHA256:
            raise ValueError("Restored executable does not match original SHA-256")
        return original
    except (KeyError, TypeError, UnicodeError, struct.error, pefile.PEFormatError) as error:
        raise ValueError("Invalid patch metadata") from error


def write_copy(source, output, restore=False):
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output or output.exists():
        raise ValueError("Output must be a new file, different from source")
    result = (restore_bytes if restore else patch_bytes)(source.read_bytes())
    with output.open("xb") as stream:
        stream.write(result)
    return sha256(result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    try:
        print("Created", args.output, "SHA-256", write_copy(args.source, args.output, args.restore))
    except (ValueError, OSError, pefile.PEFormatError) as error:
        parser.exit(1, str(error) + "\n")
