# Runtime 0.2.1 crash and correction

## Observed failure

The user reported a crash immediately after attaching 0.2.1. The client report
`Errors/2026-11-12 05.20.32 Crash - 13144.txt` records an access violation at
game RVA **0x2BE92F**, reached through **0x2C6AD4** from the BodySlider message
hook. No `C_BodySliderSL registered` line was written. No size write had occurred.

The implementation incorrectly bound `Top(lua)` to **0x2C6A60**, which is
`lua_pcall(lua, nargs, nresults, errfunc)`. Calling it with only the state pointer
interpreted uninitialized argument registers as stack counts and led to the
recorded invalid stack access. This was an implementation error, not an addon
installation error. A prior failure in 0.2 also incorrectly used Epsilon's
`lua_insert` pointer slot for `lua_type`; that revision disabled itself before
registration.

## Containment and corrected bindings

The installed 0.2.1 DLL was renamed to
`BodySliderShadowlandsRuntime-0.2.1.dll.disabled`, preventing its helper from
loading it again. The replacement is **0.2.2**:

- `lua_gettop` = game RVA **0x2C63E0**, corroborated by Epsilon slot **0x2FA520**.
- `lua_type` = game RVA **0x2C7CD0**, corroborated by Epsilon slot **0x2FA590**.
- All eight checked Epsilon slot assignments are compared with decoded
  instructions in its initialization code by `test_runtime_abi.py`.
- Wrapper targets for stack, type, number, boolean, string and table operations
  are checked in the same regression test.
- The runtime additionally checks `lua_gettop`'s expected machine-code prefix
  and validates stack bounds, 24-byte slot alignment, and the returned count
  before registration.

The original client EXE and Epsilon hooks were not changed. The corrected DLL
was deployed with SHA-256
`e6cc5f50080578697843b089ca7723cdc1233be8242a34422f29aac489a19e92`.
The unversioned attach helper was locked by its open console, so the corrected
helper is installed as **BodySliderShadowlandsAttach-0.2.2.exe**.

## Verification of the correction

- `test_lua_machine.py` executes the captured real x64 implementations of
  gettop, settop, pushnumber and pushboolean using Unicorn and a synthetic Lua
  stack. It verifies actual argument/register semantics, 24-byte slots, push
  results and positive/negative stack restoration. Capture fixture lives in the
  ignored build folder; the test explicitly skips when it is absent.
- The test-only `ShadowlandsBridgeSelfTest.dll` was loaded into disposable,
  non-login analysis clients, not the user's Epsilon session. The successful
  second run, PID **23564**, registered the actual table/functions on the Lua
  owner thread, verified stack restoration, invoked status directly, rejected an
  invalid size and handled no-player model lookup/reset. Its log is
  `build/shadowlands/Release/bridge-selftest-23564.log`.
- The test DLL does not call size application with a live player. It does not
  establish game VM invocation of DLL callbacks under Epsilon's existing
  validator behavior. The disposable process was ended after the check.
- Six targeted Python tests and four native CTest checks passed.

The standalone registration probe initially timed out before the game pumped
its window messages. Retrying with repeated bounded post messages produced the
recorded success. It was not treated as a pass until its `PASS` log existed.

## Remaining live gate

0.2.2 corrects the confirmed registration crash and is installed for a new test.
Epsilon-native callback execution, actual player size changes, preview, reset,
zoning/morphs, relog, equipment and clean exit remain **unverified**. Do not claim
0.2.1 was safe merely because its prior static/unit tests passed.
