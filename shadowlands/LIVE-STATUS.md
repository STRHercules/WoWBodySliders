# Shadowlands loader milestone - 2026-11-12

**Historical standalone-loader test.** This route does not supply Epsilon's
required launcher hooks. See [DIRECT-PATCH.md](DIRECT-PATCH.md) for the direct
patch now installed in `Wow.exe` and the pending Epsilon-launcher validation.

**The x64 diagnostic DLL loads in the supplied Epsilon 9.2.7.45745 client. Body
deformation and the Shadowlands addon bridge are not implemented yet.**

## Installed test entry point

Run `D:\Epsilon\Epsilon\_retail_\Wow-BodySlider-Shadowlands.exe`.
This is a small launcher, not a renamed/patched game binary. Keep
`BodySliderShadowlands.dll` and the original `Wow.exe` beside it. It verifies the
original's full SHA-256, starts that original executable, waits for an observed
initialized-code signature, then loads the DLL into **only that new process**.
It does not attach to an existing session, elevate privileges, or change the
original file. No launcher/realm acceptance beyond the observed test is claimed.

The launcher resolves the loader API's owning module and target module base
separately, so it does not assume fixed module addresses. A failed initialization
or DLL load is reported; the original process is not forcibly terminated.

The DLL independently verifies the executable's full digest. Its worker records
code samples at approximately 0, 5, 15 and 60 seconds. Look beside the executable
for `BodySliderShadowlands-<PID>-<UTC timestamp>.log` and corresponding `.bin`
files. These are selected code regions, not character/account memory dumps.
The DLL pins itself for its worker lifetime; close the test client before replacing
it. Saved log names use UTC. No WotLK DLL or addon should be installed as part of
this milestone.

## Live evidence

- Installed `Wow.exe` digest remained
  `c5083750b1892cf0c3a029295f3298599558a9b25c6d988c3f107b47f1aff199`.
- Final launcher SHA-256:
  `56c19d3baa77eb41ab7edcb0e04171d034badffd5f1c42d2595671e5486fa433`.
- Final DLL SHA-256:
  `84309a9ab5bbf132d91a20fae1834919cbd35f71fe78aa59fb612619e6068dac`.
- Final launcher returned success after verifying DLL module presence in its
  newly created process, PID **20768**.
- `BodySliderShadowlands-20768-20261112T092928.log` confirms the DLL worker ran,
  matched the full executable SHA-256, and read all nine selected regions.
- Earlier PID **33468** completed all four capture passes. Its 60-second samples
  are summarized in `live-code-audit.json`; every selected region differs from
  the transformed bytes in the on-disk executable.

The captured model-widget `GetModelFileID` code reads `[frame + 0x310]` before
calling RVA `0x50DCA0`. `SetModel` also tests `[frame + 0x310]`. This is a useful
model-pointer candidate, not a validated class layout. The model-related
`SetUnit` code uses a 16-byte GUID temporary and calls RVA `0x1EB61E0`; copying
the WotLK 64-bit GUID ABI would be wrong. These observations now give the next
engine-tracing pass concrete call sites and code bytes.

Captures cover x64 unwind regions, which can split a function into multiple
regions. In particular, the `SetCustomRace` sample branches beyond its first
region. Linear disassembly and a readable prologue do not validate an entire
function's behavior or a safe detour site.

## Why direct EXE patching was not retained

Two reversible patch approaches passed offline layout/restoration tests but
failed live startup before the diagnostic worker ran: adding a DLL import and
redirecting the PE entry point. The observed fault was in encrypted TLS code at
RVA `0x246EB0`. An experimental entry-prologue detour retained startup, but the
client's initializer replaced it before it could load the DLL. The initialized
entry at RVA `0xAFA60` differed from its disk bytes.

The working delivery therefore loads the DLL **after** this initialization.
Failed patch experiments are not supported installers and were removed from the
source implementation. Test artifacts are retained under the ignored build
folder rather than left as runnable test entry points in the game directory.

## Build and checks

```powershell
cmake -S shadowlands -B build/shadowlands -A x64
cmake --build build/shadowlands --config Release
ctest --test-dir build/shadowlands -C Release --output-on-failure
python -m unittest shadowlands.test_launcher shadowlands.test_profile shadowlands.test_live_samples -v
```

The native tests cover shared x64 numerical code and DLL refusal of a non-game
host. Launcher tests verify missing/unknown clients are refused before launch;
profile/capture tests verify generated input consistency and call-address
decoding. Existing audit/probe tests remain applicable. Live loader success was
checked separately from those tests.

Reproduce a code summary from captures:

```powershell
python -m shadowlands.analyze_live_samples D:/Epsilon/Epsilon/_retail_ BodySliderShadowlands-33468-20261112T092537 --second 60 --output build/shadowlands/live-code-audit.json
```

## Remaining acceptance

Lua callback registration/validation, in-world model ownership, animation and
render hooks, model profiles, actual sliders, equipment fitting, login/relog,
sharing and clean client shutdown remain unverified. The task-created diagnostic
clients used for the earlier tests were closed/ended after capture; that does
not constitute clean-exit acceptance for a functional BodySlider runtime.
