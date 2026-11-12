#include <windows.h>
#include <cassert>

int wmain(int argc, wchar_t** argv) {
    assert(argc == 2);
    HMODULE module = LoadLibraryExW(argv[1], nullptr, LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_SYSTEM32);
    assert(module);
    auto bootstrap = reinterpret_cast<int(*)()>(GetProcAddress(module, "BodySlider_Bootstrap"));
    auto status = reinterpret_cast<LONG(*)()>(GetProcAddress(module, "BodySlider_DiagnosticsStatus"));
    assert(bootstrap && status && bootstrap() == 1);
    for (int i = 0; i < 500 && status() == 0; ++i) Sleep(10);
    // A non-WoW host must never pass the client fingerprint gate.
    assert(status() == -1);
    return 0;
}
