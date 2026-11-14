"""Assemble a user-patchable distribution without redistributing Wow.exe."""

import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def package(build, patcher_build, output):
    source = Path(__file__).resolve().parent
    dll = build / "Release" / "BodySlider.dll"
    patcher = patcher_build / "Release" / "BodySliderPatch.exe"
    files = {"BodySlider.dll": dll, "BodySliderPatch.exe": patcher,
             "BodySliderCheck.exe": build / "Release" / "BodySliderCheck.exe",
             "README.md": source / "README.md", "VALIDATION.md": source / "VALIDATION.md",
             "LOGGING.md": source / "LOGGING.md"}
    files["COMPATIBILITY.md"] = source / "COMPATIBILITY.md"
    files["client_profile_report.json"] = source / "client_profile_report.json"
    addon = source / "Interface" / "AddOns" / "BodySlider"
    for item in addon.iterdir():
        if item.suffix in (".lua", ".toc", ".md"):
            files["Interface/AddOns/BodySlider/" + item.name] = item
    if output.exists():
        raise ValueError("Output already exists; choose a new archive path")
    for item in files.values():
        if not item.is_file():
            raise ValueError(f"Missing package input: {item}")
    manifest = {name: hashlib.sha256(item.read_bytes()).hexdigest() for name, item in files.items()}
    created = False
    try:
        with output.open("xb") as stream:
            created = True
            with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
                for name, item in files.items():
                    archive.write(item, name)
                archive.writestr("SHA256.json", json.dumps(manifest, indent=2) + "\n")
        with zipfile.ZipFile(output) as archive:
            assert archive.testzip() is None
            assert all(hashlib.sha256(archive.read(name)).hexdigest() == digest for name, digest in manifest.items())
            assert not any(name.lower().endswith("wow.exe") for name in archive.namelist())
    except Exception:
        if created:
            output.unlink(missing_ok=True)
        raise
    print(f"Created {output.resolve()} ({output.stat().st_size:,} bytes)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--build", type=Path, default=Path("build/native"))
    parser.add_argument("--patcher-build", type=Path, default=Path("build/patcher"))
    args = parser.parse_args()
    package(args.build, args.patcher_build, args.output)
