# Spatial-size correction, runtime 0.2.3

**Live result: unsuccessful.** The user reported no visible size change despite
successful matrix readback. See [SOURCE-0.2.4.md](SOURCE-0.2.4.md) for the current
guarded source-scale investigation. Installation details below are historical.

## Confirmed problem

The user verified that revision 0.2.2's UI slider and Lua bridge responded but
the character did not change size. Further tracing found that game RVA
`0x1385B60`, writing `model + 0x328`, is called by **SetModelAlpha** at
`0x29B33A0`. The previous size interpretation was wrong: that path controls
alpha/transparency. The earlier size-readiness message did not prove spatial
deformation.

## Installed correction

- `BodySliderShadowlandsRuntime-0.2.3.dll`
- `BodySliderShadowlandsAttach-0.2.3.exe`
- Updated `Interface/AddOns/BodySlider` using native API version **2**.

Start WoW through Epsilon as before. With the old build still loaded, type
`/bodyslider reset`, then `/reload`. Run the **0.2.3** attach helper as
administrator if Epsilon is elevated. Open `/bodyslider`, try 120%, walk, then
reset. No in-world size result is claimed until that test is observed.

The addon restores the retired API-1 baseline on load if it is still present,
then refuses to call that alpha-writing API. The new runtime replaces the old
Lua namespace with API 2 on the Lua owner thread. The old worker sees an existing
table and leaves it alone; it has no automatic native render writes of its own.
The new DLL filename permits loading without unloading the old pinned module.
The prior addon was backed up to
`build/shadowlands/addon-before-spatial-20261112T115254Z`.

## Spatial path

The unit transform routine at game RVA `0x183F510` prefers component model
`+0x30` when present, otherwise `+0x28`. It calls `0x13863D0`, which jumps to
`0x1211580`. That function copies a 4x4 spatial matrix to model `+0x100` through
`+0x13F`, then invalidates/rebuilds dependent transform state via `0x1210020`.
Those observations come from the retained initialized-code capture; they do not
by themselves establish the rendered result for the user's character.

The correction reads that matrix from the currently resolved model, validates
finite values and nonzero basis lengths, scales its first three basis vectors,
and calls the existing setter if the result differs. It preserves translation
and the matrix's remaining elements. It reads back the matrix and reports
failure if the engine did not accept it. Changes of factor are logged with
basis values for diagnosis.

The state tracks its last applied basis to prevent cumulative growth. If the
engine rebuilds an unscaled basis, it is treated as a new baseline. Reset
removes only the last known size factor, preserving current position. Replaced
models get their own baseline. The addon refreshes the local model each frame;
UI text updates remain throttled. This must still be checked for frame ordering,
movement, mounts, morphs, attached equipment and performance.

An attempted unit-transform call-site detour was **not retained**: the isolated
client refused to make that code page writable (`VirtualProtect` error 87).
Earlier suspension attempts also refused live threads with error 156. All tests
refused installation and left no active detour. The shipped correction writes
**no engine code**, changes no memory protection, and suspends no threads. It
uses the existing Lua-thread bridge and existing model setter only. No launcher
settings, original EXE bytes, server fields or packets were changed.

## Verification and limits

- Five CTest checks passed, including spatial math: translation preservation,
  repeated application without accumulation, engine baseline updates, reset,
  model replacement, and malformed matrices.
- Eight targeted Python checks passed: captured spatial/alpha ABI evidence,
  retired-API migration, addon/native readiness behavior, helper refusal, and
  Lua pointer bindings.
- The no-detour runtime bridge passed an isolated, non-login client registration
  check, PID 36240, including no-player reset refusal. This test has no actual
  in-world model and does not establish visible scaling.
- Successful matrix readback is still not proof that the rendered character
  changes. Live in-world and movement acceptance remain pending the user test.

Individual head/limb/waist/facial sliders, mesh deformation and sharing remain
unimplemented. The earlier diagnostic loading and Lua-bridge tests must not be
presented as acceptance of these features.
