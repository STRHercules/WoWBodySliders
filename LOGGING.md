# BodySlider diagnostics

Logging is enabled automatically by the DLL initializer. Look for `BodySlider.log`
beside the client executable. If that folder cannot be used, the fallback is
`%LOCALAPPDATA%\BodySlider\BodySlider.log`. If neither location works, messages go
to the Windows debugger output. No administrator privileges are required.

Every line includes UTC time, severity, process ID and thread ID. Each initialization
records the DLL build time, executable/DLL paths and client image information.
The log rotates at approximately 4 MiB, keeping the previous file as
`BodySlider.log.1`. Repeated runtime messages are limited to one per model/reason
per minute; the next emitted message reports suppressed repeats. The repeat table
holds 512 active keys; additional unique runtime messages wait for a slot to expire.
Startup errors are not subject to that limit.

The DLL reports:

- Initialization progress, supported image checks and exact signature mismatch
  addresses/bytes when client code or another hook conflicts.
- Hook installation, rollback and protection/allocation/cache failures with
  Windows error codes and descriptions.
- Lua initialization, API registration and rejected slider inputs.
- Accepted and unsupported model paths; bone counts, key mappings, parents and
  pivot differences with expected/actual values when a skeleton is rejected.
- Mesh profile acceptance and rejected vertex counts/fingerprints, with expected
  variants for a recognized model path.
- Render-device changes, stale model snapshots, invalid skin remaps, GPU buffer
  allocation/lock failures, CPU fallback and shadow batch failures.

Missing data during asynchronous model loading is informational. Unknown or
modified models are deliberately left unchanged. A logged rejection explains why
a control has no effect; it does not enable unsupported skeletons or HD models.

## DLL loading and linking

Windows can reject a DLL before its initializer runs. For missing dependencies,
wrong architecture or missing exports, close WoW and run `BodySliderCheck.exe`
beside `BodySlider.dll`. Alternatively:

```powershell
.\BodySliderCheck.exe 'C:\Games\WoW\BodySlider.dll'
```

The checker loads the DLL and its dependencies, verifies initializer export
ordinal 1, logs the result and exits. It never installs client hooks. Its log is
beside the checker, with the same fallback location. Windows code 126 means the
DLL or a dependency could not be found; 193 commonly means the wrong architecture;
127 means an entry point/export could not be found. Windows may report a missing
dependency without naming that dependency. A successful check proves loading and
export availability in the checker process, not in-game hook compatibility.

For an in-game problem, start the patched client, enter the world, use the affected
slider/model and close the client. Include `BodySlider.log` and, if present,
`BodySlider.log.1` when reporting the issue. Logs contain local executable paths
and model paths; they do not record chat, account credentials or character names.
These are diagnostic logs, not crash dumps or a guarantee of catching every
access violation. No file logging is performed inside `DllMain` or a crash handler.
