"""Generate verified Grimfall/Sirus profiles without changing either installation."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

import model_audit
import deform_audit

ROOT = Path(__file__).resolve().parent


def grimfall_key(data):
    state = struct.unpack_from("<I", data, 4)[0] ^ 264
    for shift, left in ((5, True), (17, False), (13, True)):
        value = state
        for _ in range(32 // shift + 1):
            state = (value ^ (state << shift if left else state >> shift)) & 0xffffffff
    initial = ((state - 0x3c6ef35f) * pow(0x19660d, -1, 1 << 32)) & 0xffffffff
    return initial ^ int.from_bytes(b"MD20", "little") ^ 0x9e3779b9


def decode_grimfall(data, magic=b"MD20", key=None):
    """Mirror clientextensions.dll 10015939..10015A9F on staged asset bytes."""
    if data[:4] == magic:
        return data
    expected = int.from_bytes(magic, "little")
    actual = int.from_bytes(data[:4], "little")
    mode = actual - expected
    if len(data) < 8 or mode != 2 or magic not in (b"MD20", b"SKIN"):
        raise ValueError("Unsupported encoded asset format")
    # Recover the stream state from the required version-264 first word; all tables
    # and topology are validated after decoding, so the version alone proves nothing.
    if key is None:
        if magic != b"MD20":
            raise ValueError("Encoded skin requires its model's stream key")
        key = grimfall_key(data)
    state = key ^ expected ^ 0x9e3779b9
    if state == 0:
        state = 0x1b873593
    result = bytearray(data)
    size = len(result) - 4
    whole = size // 4 * 4
    for offset in range(0, whole, 4):
        state = (state * 0x19660d + 0x3c6ef35f) & 0xffffffff
        value = (state ^ (state << 13)) & 0xffffffff
        value ^= value >> 17
        value = ((value ^ (value << 5)) + (offset // 4) * 0x17af29ac) & 0xffffffff
        struct.pack_into("<I", result, offset + 4, struct.unpack_from("<I", data, offset + 4)[0] ^ value)
    for offset in range(whole, size):
        state = (state * 0x19660d + 0x3c6ef35f) & 0xffffffff
        result[offset + 4] ^= ((state ^ (state >> 16)) >> ((offset & 3) * 8)) & 255
    result[:4] = magic
    return bytes(result)


class Client:
    def __init__(self, root, dll):
        self.root, self.dll, self.archives = root, dll, {}

    def read(self, archive, path):
        if archive not in self.archives:
            try:
                opened = model_audit.Archives(self.root, self.dll, (archive,), 0x40100)
            except OSError:
                opened = model_audit.Archives(self.root, self.dll, (archive,), 0xc0100)
            if not opened.handles:
                raise FileNotFoundError(archive)
            self.archives[archive] = opened
        return self.archives[archive].read(path)[1]

    def close(self):
        for archive in self.archives.values():
            archive.close()


def custom_header(text, namespace):
    start = text.index("struct ")
    end = text.index("inline constexpr", start)
    return text[:start].replace("namespace Stock", f"namespace {namespace}").replace("namespace Deform", f"namespace {namespace}") + text[end:].replace("// namespace Stock", f"// namespace {namespace}").replace("// namespace Deform", f"// namespace {namespace}")


def generate(clients, dll, output):
    sources = json.loads((ROOT / "client_model_sources.json").read_text())
    rigs, deforms = {"models": {}}, {"models": {}}
    report = {"models": {}, "evidence": "Offline decoded model/topology/mesh audit; live validation pending"}
    output.mkdir(parents=True, exist_ok=True)
    fixtures = output / "fixtures"
    fixtures.mkdir(exist_ok=True)
    for label, directory in clients.items():
        client = Client(directory, dll)
        try:
            for index, (path, source) in enumerate(sources[label].items()):
                identifier = label.title() + str(index)
                status = report["models"][label + ":" + path] = {"source": source}
                try:
                    encoded = client.read(source["archive"], path)
                    data = decode_grimfall(encoded) if label == "grimfall" else encoded
                    key = grimfall_key(encoded) if encoded[:4] == b"OD20" else None
                    model = dict(path=path, **model_audit.parse_model(data))
                    model["rig"] = model_audit.select_rig(model)
                    model["source_sha256"] = hashlib.sha256(encoded).hexdigest()
                    model["client"] = label
                    rigs["models"][identifier] = model
                    status.update(bones=model["bone_count"], keys=len(model["key_bones"]), rig="generated")
                    # Keep raw model fixtures local; only generated profiles are distributed.
                    (fixtures / (identifier + ".m2")).write_bytes(data)
                    if not source["skin_archive"]:
                        source["skin_archive"] = source["archive"]
                    raw = deform_audit.read_vertices(data)
                    skin_data = client.read(source["skin_archive"], path[:-3] + "00.skin")
                    if label == "grimfall":
                        skin_data = decode_grimfall(skin_data, b"SKIN", key)
                    skin = deform_audit.read_skin(skin_data, len(raw) // 48)
                    profile = deform_audit.profile(data, skin, path, all_geosets=True)
                    profile["evidence"] = "All skin geosets filtered by audited head/torso bone influence; analytic bind-geometry regions; live visual calibration pending"
                    profile["client"] = label
                    profile["variants"] = [{"kind": "raw", "count": len(raw)//48, "fingerprint": f"{deform_audit.fingerprint(raw):016x}"}]
                    combo_count, combo_offset = struct.unpack_from("<II", data, 120)
                    if combo_offset + combo_count * 2 > len(data):
                        raise ValueError("Invalid combo table")
                    combos = struct.unpack_from(f"<{combo_count}H", data, combo_offset)
                    for lod in range(4):
                        try:
                            skin_bytes = client.read(source["skin_archive"], path[:-3] + f"{lod:02}.skin")
                            if label == "grimfall":
                                skin_bytes = decode_grimfall(skin_bytes, b"SKIN", key)
                            lod_skin = deform_audit.read_skin(skin_bytes, len(raw)//48)
                            remapped = deform_audit.remapped_vertices(raw, lod_skin, combos)
                            profile["variants"].append({"kind": f"software-lod{lod}", "count": len(remapped)//48,
                                                        "fingerprint": f"{deform_audit.fingerprint(remapped):016x}"})
                        except (FileNotFoundError, ValueError) as exc:
                            status.setdefault("excluded_lods", {})[str(lod)] = str(exc)
                    deforms["models"][identifier] = profile
                    (fixtures / (identifier + ".vertices")).write_bytes(struct.pack("<I", len(raw)//48) + raw)
                    status["deform"] = "generated"
                    print(label, path, status["bones"], "bones", status["keys"], "keys", flush=True)
                except (ValueError, OSError, struct.error, StopIteration) as exc:
                    status["error"] = str(exc)
                    print(label, path, "EXCLUDED", exc, flush=True)
        finally:
            client.close()
    for filename, value in (("client_rigs.json", rigs), ("client_deforms.json", deforms), ("client_profile_report.json", report)):
        (output / filename).write_text(json.dumps(value, indent=2) + "\n")
    (fixtures / "manifest.txt").write_text("\n".join(deforms["models"]) + "\n")
    rig_header = custom_header(model_audit.generate_header(rigs), "ClientRigs")
    rig_header = rig_header.replace("namespace ClientRigs {", 'namespace ClientRigs {\nusing Stock::Rig;')
    deform_header = custom_header(deform_audit.generate_header(deforms), "ClientDeforms")
    deform_header = deform_header.replace("namespace ClientDeforms {", 'namespace ClientDeforms {\nusing Deform::Profile;\nusing Deform::Variant;')
    (output / "ClientRigs.h").write_text(rig_header)
    (output / "ClientDeforms.h").write_text(deform_header)
    print("Generated", len(rigs["models"]), "rigs and", len(deforms["models"]), "deformation profiles")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grimfall", type=Path, required=True)
    parser.add_argument("--sirus", type=Path, required=True)
    parser.add_argument("--stormlib", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    generate({"grimfall": args.grimfall, "sirus": args.sirus}, args.stormlib, args.output)
