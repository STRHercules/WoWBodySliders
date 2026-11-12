# Standalone source import

Copied the complete current `Tools/BodySlider` source from the wowdecomp workspace
into this repository. The import preserves the newer 0.3.0 DLL/addon sources,
including the live preview/preset interface and the earlier transport/bridge fixes.
The source checkout was left intact.

Included: native DLL and patcher source, embedded patch delta, addon and style
file, generated skeletal/deformation profiles, recorded audit data/evidence,
Python/native/Lua tests, audit generators and packaging code.

Isolation changes add a root CMake build, development requirements, ignored
build/release/local-input directories and repo-relative instructions. Optional
game-executable tests use an explicit environment variable; audit generators
require explicit client and StormLib paths instead of another tool's directory.
Generated headers and embedded patch data are sufficient for the normal build.

Excluded: stock/patched WoW executables, MPQs/client assets, extracted vertex test
fixtures, crash dumps/logs, installed client configuration, old release packages,
CMake caches and binaries from the original build directory. Fresh binaries and
the latest distribution can be rebuilt inside this repository; generated files
under `build` and `dist` are ignored by Git.

No remote repository is created or configured by this local import. Historical
evidence locations are preserved as provenance, not active dependencies. Live
realm compatibility, synchronization and visual acceptance are unchanged by
moving the source; consult VALIDATION.md for the retained acceptance boundaries.

Verification in this checkout: a fresh root CMake Win32 Release build produced
both binaries; all four CTest executables,32 root Python tests,9 native patcher
tests and17 Lua5.1 addon tests passed (62 checks total). Executable-dependent
tests were supplied the original via `BODYSLIDER_STOCK_EXE`, without copying it
into the repository. Native/addon source files match the imported source exactly.
`dist/BodySlider-0.3.0-prototype.zip` was generated from these fresh binaries and
the copied addon; its manifest was verified and it contains no game executable.
