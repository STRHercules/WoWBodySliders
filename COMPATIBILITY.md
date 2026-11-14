# Grimfall and Sirus compatibility test build - 1.1.1

This build adds model-specific skeleton and mesh profiles extracted from the local
Grimfall and Sirus installations on 2026-11-14. It preserves the original twenty
stock profiles. It is an offline-verified test build; live visual calibration and
realm acceptance remain separate checks.

## Coverage

- Grimfall: both sexes of all ten original races, Dark Iron, Lightforged, Zandalari,
  Dracthyr, Pandaren, Void Elf, Nightborne,
  Worgen and Vulpera, plus compatible legacy models discovered in the archives.
- Sirus: both sexes of all ten original races in stock and HD form, Pandaren,
  Void Elf, Nightborne, Worgen, Vulpera, HD Goblin, Dracthyr, Eredar, Zandalari,
  Dark Iron and Lightforged models, plus compatible legacy models.
- Sirus HD Naga: torso, primary arm pair and face controls. Leg controls are
  unavailable; no leg transforms are applied to the tail.

These are verified model paths/variants, not a claim about every realm race or
transformation. Unrecognized variants remain unchanged. Tuskarr, the legacy Naga_
models, female Broken and female Skeleton models failed the current anatomy or
file checks and remain excluded. One Sirus legacy male Skeleton supports skeletal
controls only because its supplied skin fails bounds validation.

The 1.1.1 update adds eight Grimfall variants omitted from archive listfiles and
old race-DBC joins. The logged Dark Iron male is 257 bones / 289 keys; its Sirus
variant is a distinct 263-bone model. Both remain separately validated.

The complete generated record is in `client_profile_report.json` in the source
repository, with the rig/mesh evidence in `client_rigs.json` and
`client_deforms.json`. Game models and client executables are not distributed.

## What changed

The DLL now checks every verified variant under a model path, with per-variant
bone/key counts, all key mappings, parents and pivots. HD key tables longer than
27 entries are supported without skipping validation. Mesh lookup tries all
matching profiles and still requires an exact vertex fingerprint.

The offline generator handles Grimfall's encoded models/skins in staging using
the decoder behavior observed in its client extension. This decoding code is not
loaded into the game. Installed models and archives are never replaced. The audit
distinguishes weighted landmarks from coincident unweighted helpers and derives
a missing pelvis key from the shared thigh ancestry. Client deformation regions
include all skin geosets, filtered by audited anatomical bone influence, because
these models do not consistently place the body in geoset 0.

## Install and test

1. Close the client and keep a backup of your current `BodySlider.dll`.
2. Copy this package's `BodySlider.dll` beside the patched executable you already
   use. Existing BodySlider-patched executables do not need patching again.
3. Keep/install the included addon. Run `BodySliderCheck.exe` to check DLL
   dependencies and initializer export availability.
4. Start the patched client, enter the world, then type `/bodyslider`.
5. Test one body and one facial control, reset, then check preview, equipment,
   animations, relog and exit. Share `BodySlider.log` if anything fails. A
   recognized model logs `Skeleton accepted` and `Mesh profile accepted`.

The current patcher still supports compatible build-12340 executables, including
Sirus `run.exe` and Grimfall `Wow.exe`. Do not replace a realm executable blindly;
keep the original and use the separate patched copy as before.

## Validation

Automated checks cover runtime rig selection for every generated rig, mutations
to keys beyond index 27, pivot rejection, supported skeletal controls at both
extremes, original rig behavior, decoder headers, and deterministic regeneration.
The full-mesh check uses the actual extracted vertex fixtures: every supported
body/facial control must move vertices, keep results finite, preserve UV/weights,
and reject a modified fingerprint. Native/Python patching and exact restoration
were checked against both installed executables without changing either source.

Those tests do not prove visual fit, client extension compatibility at runtime,
hardware calibration, crowded-area performance, multiplayer delivery or realm
acceptance. No game account login or live visual acceptance was performed.

## Regenerate profiles

The source generator reads the curated model/skin archive sources listed in
`client_model_sources.json`. Use a matching 64-bit Unicode StormLib build:

```powershell
python client_profiles.py --grimfall D:/Grimfall/Wotlk --sirus 'D:/Sirus/_client/World of Warcraft Sirus' --stormlib path/to/StormLib.dll --output local/generated-clients
```

Review exclusions, then copy the generated JSON evidence to the source root and
`ClientRigs.h` / `ClientDeforms.h` to `native/`. Rebuild and run the native/Python
tests. Run `build/native/Release/BodySliderClientDeformTest.exe
local/generated-clients/fixtures` for the full-mesh check. Generated raw fixtures
stay local and are excluded from the release.
