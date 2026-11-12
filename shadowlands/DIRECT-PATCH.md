# Direct Shadowlands EXE patch

**Superseded for Epsilon:** its launcher restored the original EXE before launch,
as confirmed by the user. The installed `Wow.exe` is now original again. The
tested patch remains staged in `build/shadowlands/Wow-direct-TLS.exe`. Use the
[attach-only method](EPSILON-ATTACH.md) after Epsilon starts the game. Installation
details below record the direct-patch experiment, not the current installed state.

**Installed:** `D:\Epsilon\Epsilon\_retail_\Wow.exe`.
Use the normal **Epsilon launcher**. The standalone BodySlider launcher is not
the supported Epsilon launch route.

This is still the diagnostic DLL milestone: body deformation, the addon bridge,
and functional sliders are not implemented yet.

## Patch and backup

The patch changes nine bytes in the first TLS callback's epilogue at RVA
`0x4DBF`. A relative jump enters a new read/execute `.bstls` section, preserves
integer registers and XMM0-5, aligns the stack, loads the sibling
`BodySliderShadowlands.dll`, and executes the original callback epilogue.
If the loader API or DLL is unavailable, it returns through the original
epilogue. No engine hooks are installed by this shim.

The original PE entry point, import directory, TLS directory/callback array,
ASLR settings, and existing resources remain unchanged. Section/header sizes and
checksum are updated. The original certificate bytes and directory are retained,
but modifying the file invalidates its digital signature. This does not establish
that a launcher which verifies the original signature/hash will accept the patch.

The first TLS callback runs before startup replaces the other tested patch sites.
It loads the DLL during initialization; the DLL starts a worker without waiting
under the loader lock. The worker independently checks the complete on-disk
digest and only performs diagnostics. No launcher hooks or settings are changed.

An exact original backup was created before atomic replacement:

`D:\Epsilon\Epsilon\_retail_\Wow.exe.bodyslider-original-9.2.7.45745`

| Artifact | SHA-256 |
| --- | --- |
| Original/backup | `c5083750b1892cf0c3a029295f3298599558a9b25c6d988c3f107b47f1aff199` |
| TLS-patched EXE | `17f0e43c06a2240f52552436c09379290677765d2983380553a9a9c5a7076b14` |
| Deployed DLL | `b915cdea2505935045b9921a11354bb061001f25b961ad5a0a8137014de6cfd2` |

The DLL accepts only those exact original and patched executable digests.

## Verification boundary

- A direct-patched test copy started, loaded the DLL, and produced the
  `BodySliderShadowlands-23596-20261112T102617.log` code captures. It reached a
  World of Warcraft window. This test used direct startup and does not prove
  Epsilon's launcher hooks ran.
- Offline tests verify byte-identical restoration, the expected patched digest,
  unchanged entry/import/TLS directories, rejection of tampering/unknown builds,
  and refusal to overwrite existing files.
- Unicorn tests cover rebasing, register/XMM preservation, stack alignment,
  original callback return, and missing API/DLL fallback.
- The installed original was backed up and replaced only after those checks.
- Clicking Play in the existing Epsilon launcher started `PatchLoader.exe`, PID
  33636, but no WoW process was observed during the check. The patched digest
  remained installed. **Epsilon-launcher compatibility, its own hook coexistence,
  login and gameplay remain unconfirmed.** The user was asked to try their normal
  launch procedure; launcher controls were handed back.

The older standalone-loader evidence in `LIVE-STATUS.md` is historical and is
not proof of Epsilon compatibility. New direct-patch logs continue to appear
beside the game executable. Launcher updates/repairs may replace the patched EXE;
do not assume the patch persists across an update.

## Rebuild and reproduce

```powershell
cmake -S shadowlands -B build/shadowlands -A x64
cmake --build build/shadowlands --config Release
python -m shadowlands.generate_tls_loader
python -m shadowlands.patch_tls Wow-Shadowlands.exe build/shadowlands/Wow-TLS.exe
python -m unittest shadowlands.test_patch_tls -v
```

`tls_loader_data.py` is generated from the MASM shim and checked into source so
patching does not require a compiler. Changing the shim changes the patched
digest; update the verified identity in `ClientIdentity.h` and its test only
after regenerating and validating the patch. Code output uses exclusive creation.

To reconstruct the exact original at a **new** path:

```powershell
python -m shadowlands.patch_tls D:/Epsilon/Epsilon/_retail_/Wow.exe build/shadowlands/Wow-restored.exe --restore
```

To roll back installation, close the client and replace `Wow.exe` with the exact
backup above. Keep the backup; do not overwrite it with a patched file.
