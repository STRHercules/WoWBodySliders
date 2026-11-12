# Source-scale probe and backend, revision 0.2.4

The user confirmed that **0.2.3 did not visibly change character size**. Its log
shows successful spatial-matrix readback at many factors, including 150%, but
that is not rendering acceptance. The old UI's "active" label was too strong
for what the readback proved.

## Newly traced path

The world unit update at game call sites `0x19DAAAB` and `0x19DB2EC` invokes
virtual slot `+0x60` on the native unit. It then multiplies the world matrix by
that return value through `0x1364B50`, before passing the result to `0x183F510`.
This is upstream of the matrix write attempted by 0.2.3. That evidence supports
investigating the source scale instead of repeatedly writing a derived matrix.

Runtime 0.2.4 reads that live virtual slot and accepts only one of four previously
decoded leaf implementations, each exactly `movss xmm0, [rcx+offset]; ret`:

| Getter RVA | Float offset |
| --- | --- |
| `0x1760820` | `0x3E0` |
| `0x1864690` | `0x3D0` |
| `0x18D2FC0` | `0xD8` |
| `0x19D3A90` | `0xF8` |

The runtime verifies the live target and all nine machine-code bytes, bounds the
decoded offset, and validates the current float. **The correct implementation
for the user's live unit is not yet known.** If it is not on the allowlist,
application returns false, logs the vtable/getter RVAs, and makes no scale write.

For an accepted implementation, the source value is adjusted with the existing
baseline/reset logic and read back. The spatial setter remains for immediate
refresh. No executable bytes, process protections, launcher settings or network
packets are changed. This is still a client-memory prototype; visual behavior,
local bounds, movement and equipment implications remain unverified.

## Delivery and safe diagnostic first step

Installed files:

- `D:\Epsilon\Epsilon\_retail_\BodySliderShadowlandsRuntime-0.2.4.dll`
- `D:\Epsilon\Epsilon\_retail_\BodySliderShadowlandsAttach-0.2.4.exe`
- Updated addon TOC/Lua files, version `0.2.4-shadowlands-prototype`.

The addon requires `C_BodySliderSL.Backend() == 3`; the public `Status()` version
stays 2 so older workers will not repeatedly replace the newer namespace. A new
backend starts at **100%** rather than automatically applying the user's prior
failed experimental size. That old setting is retained as `previousSize` in the
same per-character SavedVariables record. Older alpha/matrix-only backends are
reset during addon load, then refused. Their loaded modules need not be unloaded.

The previous addon is backed up under
`build/shadowlands/addon-before-source-20261112T120441Z`.

The user was asked only to `/reload` and attach 0.2.4 while leaving size at 100%,
so the live getter can be inspected before another visual test. At that neutral
setting, the source-scale write is skipped. The runtime logs either
`Source scale getter verified` or `Source scale refused` with the observed RVA.
Do not claim 0.2.4 solved rendering before that observation and a visual test.

## Checks

- Five CTest checks pass, including baseline/reset and spatial math.
- Ten targeted Python checks pass, including exact getter machine-code evidence,
  retired backend migration, neutral startup and preserved prior setting.
- The isolated, non-login bridge self-test passed in PID 37792. It verifies
  registration and missing-player refusal, not a source write to a live player.
- Deployment was completed; the original `Wow.exe` was not edited.
