# Shadowlands 0.2: Lua bridge, size control and preview

**Current revision: [0.2.3](SPATIAL-0.2.3.md).** Revision 0.2.2's alleged size
setter was identified as alpha/transparency and has been replaced by the spatial
matrix path. The size implementation details below describe the earlier attempt,
not verified spatial behavior. Revision 0.2.1 crashed during Lua registration and
has been disabled. See [CRASH-0.2.1.md](CRASH-0.2.1.md) for the cause, fix and
isolated registration evidence. Use the versioned
`BodySliderShadowlandsAttach-0.2.3.exe` and `BodySliderShadowlandsRuntime-0.2.3.dll`
now installed in the client folder. Live size behavior remains pending.

This is the first functional-control implementation after the diagnostic loader.
It implements **local-player overall render size**, 50–150%, and a model-preview
window. It is not the 37-control WotLK port. Head/limb/waist/face controls, vertex
deformation, calibrated rigs and sharing remain unimplemented.

**Build/unit checks have passed. In-game Lua registration, size change, reset and
preview correctness are pending the user's live test.** Do not equate module
loading or numerical tests with visual acceptance.

## Test the installed version

1. Launch the game normally through Epsilon.
2. Run `D:\Epsilon\Epsilon\_retail_\BodySliderShadowlandsAttach.exe` as
   administrator if Epsilon is elevated. It now loads
   `BodySliderShadowlandsRuntime.dll`. The earlier diagnostic DLL may remain
   loaded; the new filename permits loading this runtime without unloading it.
3. Type `/reload`, then `/bodyslider`.
4. The slider stays disabled until the native bridge answers and a supported
   player render model is available. Try a small change such as 105%, inspect
   the actual in-world player and preview, then press **Reset size**.
5. `/bodyslider status` prints readiness; `/bodyslider reset` also resets size.

The UI uses the existing BodySlider gold/ink palette and Friz Quadrata font.
Mouse wheel changes preview distance. Settings are stored under
`BodySliderDB.shadowlands[realm .. ":" .. UnitGUID("player")].size`. Other
BodySlider settings and presets are preserved. The preceding installed addon was
backed up under `build/shadowlands/addon-before-runtime-20261112T111338Z`.

The native worker writes `BodySliderShadowlandsRuntime-<PID>-<UTC timestamp>.log`.
Look for `C_BodySliderSL registered on the game window thread`. Identity/API/ABI
mismatches disable the bridge and are logged. Module presence alone does not
prove registration. If a runtime DLL has already been loaded and then rebuilt,
close the game before replacing it; there is no hot-unload path.

## Native implementation and evidence

The original `Wow.exe` remains unchanged. The attach helper requires Epsilon's
module to be present; it never starts the game itself. The runtime checks:

- Full executable digest against the pinned source build (or the previously
  tested TLS-patched diagnostic copy).
- EpsilonAddon.dll digest
  `b3fba2a4059212bebc11c9bcc104b1b008c236cf156ab89014386748cd299fb8`.
- Seven Lua API pointer slots initialized by Epsilon at DLL RVAs
  `0x2FA470`, `0x2FA478`, `0x2FA4F8`, `0x2FA550`, `0x2FA558`, `0x2FA5A0`,
  `0x2FA5B0` against their expected ASLR-adjusted game addresses.
- Original bytes at the Lua-state getter, unit-token resolver, model accessor
  and render-scale setter.

The Lua registration sequence is based on Epsilon's existing namespace
registration code at DLL RVA `0x29D40`. Its initialization at `0x29740` populates
the Lua API pointers. This runtime **does not modify Epsilon's validator patches
or detour engine code**. It installs a `WH_GETMESSAGE` hook on its own game's
window thread and posts a registered message. Before touching Lua it calls the
engine's Lua-owner-thread predicate at RVA `0x5FD640`. The Lua stack top is
preserved across registration. Polling recreates the namespace after UI reloads.

The namespace `C_BodySliderSL` exposes `Status()`, `SetSize(factor)` and `Reset()`.
The addon checks the API version and handles attachment after login. It does not
turn controls on merely because a function name exists.

The model path is traced from these initialized-code observations:

- Lua `UnitIsVisible` at RVA `0x208CAA0` resolves a unit token through
  `0x206F1B0(token, 0)`.
- `CPlayerModel::SetUnit` code at `0x1EB6A60` uses the returned typed unit wrapper,
  reads its native pointer at `+8`, and calls the render-model accessor.
- That accessor, RVA `0x18329B0`, reads `[native + 0x20]`, then `[component + 0x28]`.
- Getter `0x13848D0` reads a float at model `+0x328`; setter `0x1385B60` writes
  the same float. The player-model clone path calls those methods.

Those functions were inspected from an initialized analysis-only process; this
is static/runtime-code evidence for the binding, not a recorded visual size
test. The private code snapshot and its identity are under the ignored
`build/shadowlands/initialized-text-late.*`. This process was ended after capture;
it was not used to claim Epsilon launch or gameplay acceptance.

The implementation resolves the current player/model afresh on each application
and validates memory reads and the model vtable range. It never dereferences an
old cached model pointer. The baseline logic avoids multiplying an already
applied value again, adopts a new baseline if the engine changes scale, and
restores on reset. A transient missing model retains the old baseline without
writing through it. New models get their own baseline. The addon requests reset
on leaving the world/logout and when binding a fresh API table.

Overall render scaling is client-local. No chat commands, network packets,
server attributes or collision fields are modified. Individual bone proportions
will need separate lifecycle/animation/rig work; a uniform-size result does not
validate those paths.

## Checks

```powershell
cmake -S shadowlands -B build/shadowlands -A x64
cmake --build build/shadowlands --config Release
ctest --test-dir build/shadowlands -C Release --output-on-failure
python -m unittest shadowlands.test_addon shadowlands.test_launcher -v
```

The size-state assertions exercise no accumulation, reset, external scale
updates, replacement models and invalid inputs. Lua tests exercise saved-value
sanitization, late attachment, readiness failures, reset and the window/slider
connection with mocked widgets. Mock tests do not verify actual FrameXML
templates, visual layout or preview cloning. Live acceptance still includes
movement, mounts/morphs, equipment, zoning, UI reload, relog and clean exit.
