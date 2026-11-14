#include "Logging.h"

int wmain(int argc, wchar_t** argv) {
    wchar_t library[32768]{};
    if (argc > 2) { std::puts("Usage: BodySliderCheck.exe [path to BodySlider.dll]"); return 1; }
    if (argc == 2) {
        DWORD size = GetFullPathNameW(argv[1], static_cast<DWORD>(std::size(library)), library, nullptr);
        if (!size || size >= std::size(library)) {
            Diagnostics::WinError("Cannot resolve DLL path"); return 1;
        }
    } else {
        DWORD size = GetModuleFileNameW(nullptr, library, static_cast<DWORD>(std::size(library)));
        if (!size || size >= std::size(library)) { Diagnostics::WinError("Cannot resolve checker path"); return 1; }
        wchar_t* slash = std::wcsrchr(library, L'\\');
        if (!slash || wcscpy_s(slash + 1, std::size(library) - (slash + 1 - library), L"BodySlider.dll")) return 1;
    }
    Diagnostics::Log("INFO", "=== DLL linkage check: %ls ===", library);
    // Load dependencies and verify the export; never run client hooks in the checker process.
    HMODULE module = LoadLibraryExW(library, nullptr, LOAD_WITH_ALTERED_SEARCH_PATH);
    if (!module) {
        Diagnostics::WinError("DLL LoadLibraryEx failed");
        std::puts("DLL load failed. See BodySlider.log (or %LOCALAPPDATA%/BodySlider/BodySlider.log). Common codes: 126 missing DLL/dependency, 193 wrong architecture.");
        return 1;
    }
    auto initialize = GetProcAddress(module, MAKEINTRESOURCEA(1));
    if (!initialize) Diagnostics::WinError("DLL initializer ordinal 1 missing");
    else Diagnostics::Log("INFO", "DLL loaded successfully module=%p initializer=%p; client hooks not invoked", module, initialize);
    if (!FreeLibrary(module)) { Diagnostics::WinError("DLL FreeLibrary failed"); return 1; }
    std::puts(initialize ? "DLL dependencies and initializer export OK. In-game hook/skeleton checks require WoW; see BodySlider.log."
                         : "DLL initializer export missing. See BodySlider.log.");
    return initialize ? 0 : 1;
}
