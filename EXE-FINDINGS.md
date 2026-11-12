# Executable-only investigation, 2026-11-12

Target: supplied 9.2.7.45745 PE32+, SHA-256
`c5083750b1892cf0c3a029295f3298599558a9b25c6d988c3f107b47f1aff199`.

## Important correction to the initial scan

Readable API strings and name/function pairs survive in this file, but their
function bodies are not usable ordinary x64 code on disk. For example,
`UnitGUID` at RVA `0x20C49C0` starts with
`21 67 a6 f8 d8 b4 a5 c1 58 27 2c 7b`, and `CreateFrame` at RVA `0x29E49A0`
starts with `7a aa 72 1c ef b6 24 7c`. These raw bytes are not verified function
prologues. The entire `.text` section has entropy approximately **7.99995 bits
per byte**. High entropy alone does not prove encryption, but the combination
with the startup observations below supports transformed/protected code.

The original report's unwind entries corroborate table targets only. They do
not validate an engine calling contract, identify safe detour bytes, or prove
that raw disassembly is meaningful. `exe-audit.json` now marks all candidates
`callable_verified: false`. No hooks should be installed from this inventory.

## API neighborhoods narrow the model targets

`audit_exe.py` now groups adjacent name/function pairs and preserves their names
and RVAs. These are bounded contiguous neighborhoods and can include multiple
adjacent registration tables; they do not establish C++ class ownership.

| Candidate | Evidence | Implication |
| --- | --- | --- |
| `SetUnit` at `0x1EB24D0` | Its neighborhood starts at pair RVA `0x33BA660` and includes `SetCreature`, `SetDisplayInfo`, `SetCustomRace`, and model-camera methods | Stronger preview/player-model lead |
| `SetUnit` at `0x20247A0` | Neighbors include `SetTradeTargetItem`, `SetBagItem`, `SetUnitBuff`, `SetUnitDebuff`, and `NumLines` | Tooltip-related lead; unsuitable as a model assignment hook without further evidence |
| `SetModel` at `0x29B1B80` | Neighborhood `0x33DE380` includes `SetPosition`, `SetFacing`, `SetModelScale`, `SetSequence`, and `SetCamera` | General model-widget method table candidate |
| `GetModelFileID` at `0x1F63840` | Neighbors include `GetModelUnitGUID`, `SetYaw`, `SetScale`, and `SetAnimation` | Separate model-scene actor table candidate |
| `Undress` / `TryOn` | Neighborhood `0x33C5410` contains dress/appearance methods | Equipment-preview lead |

These narrow where to resume tracing after obtaining readable code. They do not
identify the in-world character's skeleton, vertex buffer, or lifetime manager.

## Offline startup probe

`probe_startup.py` emulates the supplied TLS callbacks with Unicorn. The game
is not launched. Local x64 `ntdll.dll`, `kernel32.dll`, and `kernelbase.dll` are
read for their export metadata; the emulator stops before executing their code.
Only success returns for `VirtualProtect` and vectored-handler registration are
modeled. Other external calls stop analysis. System-module hashes are retained
in `startup-probe.json`; results depend on this synthetic environment.

Observed in the saved probe:

1. The initial TLS callback array is `0x3D20`, `0x246EB0`, `0x28940F8`.
2. Calling the first callback rewrites the list to `0x2B6B60`, `0x9D30`,
   `0x2B6A60`, `0x246EB0`, `0x28940F8`. The next array entry is re-read after
   each callback, rather than trusting the original list.
3. The first callback requests `VirtualProtect` on the callback list for
   `0x110` bytes with protection `4`, then restores the modeled prior protection.
4. The next callback, now `0x9D30`, registers a vectored exception handler at
   `0x2B150` with first-handler priority.
5. It reaches `HLT` at `0xCA4C`. The handler accepts a synthetic privileged-
   instruction exception (`0xC0000096`) and sets trap-flag stepping. Subsequent
   synthetic single-step exceptions (`0x80000004`) are accepted by that handler.
6. The saved run stops at its explicit **128-exception limit**. It has not
   completed startup or produced a readable engine image.

This establishes exception-driven startup behavior in emulation. It does not
establish successful decryption, actual Windows behavior, or compatibility with
game launchers/realm checks. Integer registers and flags are preserved in the
synthetic exception context; SIMD, debug-register and full Windows loader state
are not modeled. Unknown API calls and execution limits remain explicit stops.

## Reproduce

The optional dependency is isolated from the game/runtime and normal build:

```powershell
python -m pip install -r shadowlands/requirements-analysis.txt
python -m unittest shadowlands.test_probe_startup shadowlands.test_audit_exe -v
python shadowlands/probe_startup.py Wow-Shadowlands.exe --max-exceptions 128 --output build/shadowlands/startup-probe.json
```

Output files must be new. `--seconds` bounds emulation to 1–60 seconds and
`--max-exceptions` bounds exception dispatches to 0–10,000. Every emulation call
also has an instruction limit. The CLI writes a report, not a patched EXE or
memory dump. A zero-exception test verifies callback rewriting, handler discovery,
the first fault, and the unchanged input digest.

## Next engine milestone

Readable post-initialization code is needed before implementing engine hooks.
Continuing offline exception/loader reconstruction may recover it; alternatively
a permitted running client can provide the initialized image. The EXE alone has
not yet supplied that image. Full game data is still unnecessary for this loader
investigation, but is required for later model calibration and live acceptance.
