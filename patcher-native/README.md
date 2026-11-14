# BodySliderPatch.exe

Small native Windows patcher; no Python or VC runtime installation is needed.

Double-click it and select the build 12340 executable (including renamed/customized clients). It
creates `Wow-BodySlider.exe` in the same folder. It never changes the selected
file or overwrites an existing output. Close WoW, preserve your original, then
rename the new copy to `Wow.exe` when installing the DLL/addon. Selecting an
unchanged BodySlider-patched copy instead creates `Wow-original.exe`.

The file version must be 3.3.5.12340. The patcher validates x86 PE32, fixed base 0x400000, disabled ASLR, standard PE alignment, spare section-header space, and the two required KERNEL32 imports. It resolves loader import addresses from each input instead of requiring a stock file hash. Malformed files, other builds, and files changed after patching are rejected.

For scripted use:

```powershell
BodySliderPatch.exe --patch input/Wow.exe output/Wow.exe
BodySliderPatch.exe --restore patched/Wow.exe restored/Wow.exe
```

The file format is byte-for-byte compatible with the Python reference patcher.
The native program embeds only the loader stub. It derives header changes and SHA-256 restoration metadata from the selected input, preserving original code, resources, and overlays. Restoration verifies the patched body and recovered original digest. Windows Unicode file APIs preserve non-ASCII paths.

Build and test from the repository root:

```powershell
cmake -S . -B build -A Win32
cmake --build build --config Release
$env:BODYSLIDER_STOCK_EXE = 'C:/Games/WoW-original/Wow.exe'
python patcher-native/test_native_patcher.py
```

`PatchData.h` is generated with `python patcher-native/generate_patch_data.py`; no stock executable is needed. Regenerate it and rerun tests whenever the reference loader changes.

The automated tests cover the command-line path. An interactive smoke check
verified that the native file picker opens correctly and Cancel closes it without
writing files. Selecting a file and completing patching through that dialog has
not been tested; its conversion function is the same one used by the CLI.
Realm acceptance of the resulting modified client is independent of whether
patching and restoration succeed.
