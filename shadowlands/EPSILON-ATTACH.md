# Epsilon-compatible loading path

**Runtime 0.2 update:** use `BodySliderShadowlandsRuntime.dll` with the updated
attach helper. It implements the Lua bridge and an overall-size prototype plus
preview UI; see [RUNTIME-0.2.md](RUNTIME-0.2.md). The diagnostic-only descriptions
and logs below record the earlier milestone.

**Launch WoW through Epsilon first**, then run
`D:\Epsilon\Epsilon\_retail_\BodySliderShadowlandsAttach.exe` at the same
elevation as Epsilon. In the tested setup Epsilon's process denies normal-user
process access, so right-click the helper and choose **Run as administrator**.
This agent cannot approve that Windows elevation prompt for you.

Keep `BodySliderShadowlandsRuntime.dll` beside the helper. The helper does not start
WoW, alter the launcher, disable updates, or patch an executable. It selects a
running `Wow.exe` from the same folder, checks its exact file digest, verifies
`EpsilonAddon.dll` is already present, and then loads BodySlider into that
existing process. It does not replace or unload Epsilon's hooks. If multiple
matching clients are running, supply the intended PID as its sole command-line
argument; otherwise it refuses to choose one.

The current DLL only records diagnostic code captures. **Functional sliders,
Lua integration and deformation hooks are still pending.** Loading alongside
Epsilon is a required acceptance gate, not proof that future hooks will coexist.

The helper now appends a timestamped result, target PID and explanation to
`BodySliderShadowlandsAttach.log` beside the executable. When opened in its own
console, it waits for Enter so success or failure remains readable. When run
from an existing terminal it returns normally with its exit code.

## Why patching Wow.exe alone does not work here

The direct TLS patch passed its standalone startup test: it loaded the DLL and
captured initialized engine code, and restoration is byte-identical. However,
Epsilon replaced the patched file before launching the game. The user confirmed
the replacement came from Epsilon rather than a manual restore.

The installed `Wow.exe` was rechecked and matches the original digest
`c5083750b1892cf0c3a029295f3298599558a9b25c6d988c3f107b47f1aff199`.
It has been left that way. The original backup also retains that digest.
The tested direct patch is staged at
`build/shadowlands/Wow-direct-TLS.exe`, SHA-256
`17f0e43c06a2240f52552436c09379290677765d2983380553a9a9c5a7076b14`.
It is not the persistent delivery method for this launcher.

## Current verification

- The attach helper found the actual Epsilon-launched client, PID 9988.
- Windows returned `OpenProcess` error **5 (access denied)** from this agent's
  normal-privilege session. The helper exited with code 9 and made no client
  changes. The user was asked to run it at Epsilon's elevation.
- The user's elevated run subsequently succeeded. The diagnostic DLL log
  `BodySliderShadowlands-9988-20261112T104429.log` confirms the worker ran in the
  Epsilon-launched client, matched the original full EXE hash, and completed all
  four code-capture passes through 60 seconds. The helper checks EpsilonAddon
  before injection. This verifies diagnostic co-loading, not deformation behavior.
- The previous standalone launcher was retired and moved out of the client
  folder. Its source was replaced by the attach-only helper.

On a successful load, `BodySliderShadowlands-<PID>-<UTC timestamp>.log` appears
beside `Wow.exe`. It confirms the worker's executable identity check and code
capture status. The console reports `DLL module load: verified`; this verifies
module presence, while the log verifies that the diagnostic worker ran.
If already loaded, the helper does not load a second copy. Close the client
before updating the DLL because the diagnostic worker pins its module.

## Shadowlands addon status

The WotLK addon reports a missing patched EXE/DLL because it expects native Lua
functions that this Shadowlands DLL does not implement. Successful DLL loading
alone cannot satisfy those checks. A Shadowlands diagnostic TOC (`90207`) and
`Status.lua` are now installed in the existing `Interface/AddOns/BodySlider`
folder. After `/reload`, `/bodyslider` reports that functional sliders are not
available and directs the user to the attach log. It does not claim that it can
detect native attachment from Lua.

The original installed addon files were backed up to
`build/shadowlands/installed-addon-backup-20261112T104728Z`. Only the TOC was
replaced and `Status.lua` added; the old Lua files remain on disk but are not
loaded by the diagnostic TOC. Existing SavedVariables were not edited. Actual
in-game slash-command acceptance remains for the user's reload test.

## Build and checks

```powershell
cmake -S shadowlands -B build/shadowlands -A x64
cmake --build build/shadowlands --config Release
ctest --test-dir build/shadowlands -C Release --output-on-failure
python -m unittest shadowlands.test_launcher -v
```

The unit test checks missing/unknown file refusal without starting a game.
The native DLL test checks refusal of an unrelated executable. Windows access
denial and cross-module loading must additionally be checked on the actual
Epsilon-started client; no privilege boundary is bypassed by the helper.
