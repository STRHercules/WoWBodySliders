# Body Slider for Shadowlands - first size-control prototype

**Current build:** [runtime 0.2.4](SOURCE-0.2.4.md) investigates the upstream
unit source-scale getter. The user confirmed that 0.2.3's matrix writes did not
visibly change size. No current visual-size success is claimed. It includes the game-thread Lua bridge,
local-player overall-size control, reset, saved settings and model-preview UI.
Its build/unit checks pass; in-game slider and visual acceptance are pending.
Individual body/face proportions and sharing are not implemented yet.

**Current Epsilon delivery is an [attach-only helper](EPSILON-ATTACH.md).** Start
the game through Epsilon, then load the DLL into that process. Epsilon restores
direct EXE patches; the standalone launcher did not supply Epsilon's required hooks.

Target: the supplied **9.2.7.45745 x64** `Wow-Shadowlands.exe`.
SHA-256: `c5083750b1892cf0c3a029295f3298599558a9b25c6d988c3f107b47f1aff199`.

This folder contains a separate Shadowlands backend, native runtime/attach helper,
executable audit, bounded offline TLS probe and numerical tests.
Read [RUNTIME-0.2.md](RUNTIME-0.2.md) and [EPSILON-ATTACH.md](EPSILON-ATTACH.md) for current
installation and validation limits; [DIRECT-PATCH.md](DIRECT-PATCH.md) and
[LIVE-STATUS.md](LIVE-STATUS.md) record the earlier experiments.
The WotLK runtime, patcher, addon and package are unchanged.

## What is working

- `audit_exe.py` accepts only the supplied executable's exact digest, checks its
  PE64 architecture/version, inventories sections/imports, and searches selected
  Lua/model API names for aligned name/function pointer pairs.
- Candidate function pointers must point to executable code with an x64 unwind
  function entry. The report retains the pair location, function range, and a
  short disassembly prefix. All addresses except the preferred image base are
  RVAs: runtime addresses must use the actual module base, not `0x140000000`.
- `exe-audit.json` records the current scan and adjacent API-table neighborhoods. Names with no candidates are bounded
  search results, not evidence that an API is absent. Different table layouts,
  code references, and dynamically initialized entries are not scanned.
- The code section appears transformed on disk; candidate pointers are **not
  callable-verified hooks**. The startup probe reproduced callback rewriting and
  exception-driven control flow in a synthetic environment. Read
  [EXE-FINDINGS.md](EXE-FINDINGS.md) and `startup-probe.json` for evidence and limits.
- A later live pass loaded `BodySliderShadowlands.dll` after initialization and
  captured readable code. `live-code-audit.json` records selected samples and
  call targets. They remain analysis leads, not verified deformation hooks.
- The existing shape and deformation numerical tests build and pass as x64
  programs. They reuse WotLK fixture profiles; they do **not** establish that
  Shadowlands model layouts or profiles are supported.

The audit reads the input and never executes or patches it. JSON output uses
exclusive creation and refuses to overwrite any existing file.

## Initial executable evidence

The supplied PE32+ image enables ASLR and has 195,915 x64 runtime-function entries.
Its normal import table contains only `USER32.dll!MessageBoxW`. This does not
establish how its remaining APIs are resolved, or that it is an unmodified client.
The WotLK loader's fixed addresses and 32-bit bootstrap cannot be reused.

Selected name/function table candidates:

| Name | Function RVA | Pair RVA |
| --- | --- | --- |
| `UnitGUID` | `0x20C49C0` | `0x2E1D480` |
| `UnitName` | `0x20C58D0` | `0x2E1D490` |
| `UnitRace` | `0x20E6C90` | `0x2E1D640` |
| `CreateFrame` | `0x29E49A0` | `0x33DF6B0` |
| `SetModel` | `0x29B1B80` | `0x33DE380` |
| `SetUnit` | `0x1EB24D0`, `0x20247A0` | See JSON |
| `GetModelFileID` | `0x1F63840`, `0x29B1CA0` | See JSON |

Table ownership, calling contracts and behavior remain unverified. The second
`SetUnit` candidate is adjacent to tooltip methods; it is not equivalent to the
first model-related candidate. These are
entry points for tracing object lookup, model assignment and Lua registration,
not addresses to install detours at. No skeleton-animation or vertex-buffer hook
has been established. The available REA native-analysis service is not connected
in this session; this investigation uses pefile, Capstone and optional Unicorn directly.

## Build and verify

Run from the repository root with Python 3 and MSVC x64/Windows SDK installed.
The Python dependencies `pefile` and `capstone` are already in the repository's
`requirements-dev.txt`; no new dependencies are introduced.

```powershell
python -m unittest shadowlands.test_audit_exe -v
python shadowlands/audit_exe.py Wow-Shadowlands.exe --output build/shadowlands-exe-audit.json
cmake -S shadowlands -B build/shadowlands -A x64
cmake --build build/shadowlands --config Release
ctest --test-dir build/shadowlands -C Release --output-on-failure
```

Choose a new report filename if it already exists. The Python tests use a synthetic
PE64 fixture to check candidate discovery and rejection of invalid pointers and
file overlays. An additional test audits the supplied executable and verifies its
digest is unchanged; set `BODYSLIDER_SHADOWLANDS_EXE` to use a different location.
Only that integration test skips when the EXE is unavailable; an existing file
with the wrong digest fails.

## Remaining adaptation

1. Trace the candidate tables to establish Lua registration, player GUID/object
   lookup, model ownership and the native callback rules. The existing native
   `uint64_t` GUID parser and addon's `0x`-hex GUID validation are WotLK-specific;
   Shadowlands needs its own observed identity mapping.
   Selected post-initialization code has now been captured through the
   diagnostic DLL. Trace those samples and their callees before installing hooks.
2. Map skeleton animation, model destruction and render-buffer lifetimes. Build
   an ASLR-aware x64 loader/hook implementation with original-byte checks,
   rollback and refusal of unknown builds. The existing x86 inline assembly and
   five-byte trampoline implementation cannot simply be rebuilt for x64.
3. Extract matching character skeletons, meshes and skin data. Calibrate one
   race/sex and prove skeletal sliders first, then vertex deformation. Keep the
   shared numerical code; do not enable the stock WotLK profiles on HD models.
4. Adapt the addon for Shadowlands GUID strings, `C_ChatInfo` messaging, group
   APIs, widget behavior and model previews. Retain the 37-control preset wire
   format where its semantics still apply. Verify against matching FrameXML.
5. Verify in-game animations, armor, attachments, mounts, shadows, model reloads,
   device resets and clean exit, then multi-client sharing and performance.

## Do you need a full installation?

**Not for the current EXE stage.** The executable allows build identification,
static disassembly, candidate/API-table discovery and design of the x64 native
backend. It does not include the character meshes or prove runtime behavior.

Matching client data is needed for model work: the relevant CASC character M2,
skin and skeleton resources and their dependencies, plus mapping metadata where
needed. Selected extracted assets can be enough to start one profile; supplying
the EXE alone is not enough to calibrate one. Matching FrameXML helps verify addon
API changes. A complete runnable 9.2.7.45745 client is the practical requirement
for launch/login/rendering tests. It must include the data used by the test
character; a partial streaming installation may need to download missing assets.
A matching realm/login environment is needed for in-world acceptance.

Realm acceptance of a modified client remains untested. Static tests and a
successful x64 build do not establish that the game will load or accept hooks.
