// Included by BodySliderShadowlands.cpp inside its implementation namespace.

namespace Runtime {
struct Lua;
using Function = int (*)(Lua*);
unsigned char* g_base = nullptr;
HHOOK g_hook = nullptr;
HWND g_window = nullptr;
UINT g_message = 0;
bool g_threadReported = false;
const char* g_last = "Waiting for an in-world player";

template<class T> bool Read(const void* pointer, T& output) {
    SIZE_T count = 0;
    return pointer && ReadProcessMemory(GetCurrentProcess(), pointer, &output, sizeof(T), &count) && count == sizeof(T);
}
template<class T> T Api(uintptr_t rva) { return reinterpret_cast<T>(g_base + rva); }
auto State = []() { return Api<Lua*(*)()>(0x5FCC40)(); };
auto Top = [](Lua* lua) { return Api<int(*)(Lua*)>(0x2C63E0)(lua); };
auto SetTop = [](Lua* lua, int top) { Api<void(*)(Lua*, int)>(0x2C7840)(lua, top); };
auto Type = [](Lua* lua, int index) { return Api<int(*)(Lua*, int)>(0x2C7CD0)(lua, index); };
auto Number = [](Lua* lua, int index) { return Api<double(*)(Lua*, int)>(0x2C7BC0)(lua, index); };
auto PushNumber = [](Lua* lua, double value) { Api<void(*)(Lua*, double)>(0x2C6DE0)(lua, value); };
auto PushBool = [](Lua* lua, bool value) { Api<void(*)(Lua*, int)>(0x2C6B30)(lua, value); };
auto PushString = [](Lua* lua, const char* text) { Api<void(*)(Lua*, const char*)>(0x2C6E00)(lua, text); };
auto SetTable = [](Lua* lua, int index) { Api<void(*)(Lua*, int)>(0x2C71A0)(lua, index); };
auto Pcall = [](Lua* lua, int arguments, int results, int error) { return Api<int(*)(Lua*, int, int, int)>(0x2C6A60)(lua, arguments, results, error); };

SpatialSize::State g_spatial;
BodySize::State g_sourceScale;

void* PlayerNative() {
    void* unit = Api<void*(*)(const char*, int)>(0x206F1B0)("player", 0);
    void* native = nullptr;
    return unit && Read(static_cast<unsigned char*>(unit) + 8, native) ? native : nullptr;
}

float* ScaleSource(void* native) {
    uintptr_t table = 0, getter = 0;
    unsigned char code[9]{};
    if (!native || !Read(native, table) || !Read(reinterpret_cast<void*>(table + 0x60), getter)) return nullptr;
    uintptr_t rva = getter - reinterpret_cast<uintptr_t>(g_base);
    bool known = rva == 0x1760820 || rva == 0x1864690 || rva == 0x18D2FC0 || rva == 0x19D3A90;
    SIZE_T count = 0;
    if (!known || !ReadProcessMemory(GetCurrentProcess(), reinterpret_cast<void*>(getter), code, 9, &count)
            || count != 9 || std::memcmp(code, "\xF3\x0F\x10\x81", 4) || code[8] != 0xC3) {
        static uintptr_t logged = 0;
        if (getter != logged) {
            char message[256]{};
            sprintf_s(message, "Source scale refused: native vtable RVA=0x%llX, scale getter RVA=0x%llX.",
                      static_cast<unsigned long long>(table - reinterpret_cast<uintptr_t>(g_base)), static_cast<unsigned long long>(rva));
            Log(message); logged = getter;
        }
        return nullptr;
    }
    uint32_t offset = 0; std::memcpy(&offset, code + 4, 4);
    if (offset < 0x20 || offset > 0x1000) return nullptr;
    static uintptr_t loggedGetter = 0;
    if (getter != loggedGetter) {
        char detail[256]{};
        sprintf_s(detail, "Source scale getter verified: RVA=0x%llX, native float offset=0x%X.",
                  static_cast<unsigned long long>(rva), offset);
        Log(detail); loggedGetter = getter;
    }
    return reinterpret_cast<float*>(static_cast<unsigned char*>(native) + offset);
}

void* PlayerModel() {
    // UnitIsVisible calls this resolver with (unit token, 0); it returns the typed unit wrapper.
    void* unit = Api<void*(*)(const char*, int)>(0x206F1B0)("player", 0);
    void* native = nullptr;
    void* component = nullptr;
    void* model = nullptr;
    // CPlayerModel's SetUnit path calls GetRenderModel(native), which reads +20 -> +28.
    if (!unit || !Read(static_cast<unsigned char*>(unit) + 8, native) || !native
            || !Read(static_cast<unsigned char*>(native) + 0x20, component) || !component) return nullptr;
    // Unit transform update prefers the alternate render model at +30 when present.
    if (!Read(static_cast<unsigned char*>(component) + 0x30, model)) return nullptr;
    if (!model && !Read(static_cast<unsigned char*>(component) + 0x28, model)) return nullptr;
    if (!model) return nullptr;
    uintptr_t vtable = 0;
    uintptr_t offset = 0;
    if (!Read(model, vtable)) return nullptr;
    offset = vtable - reinterpret_cast<uintptr_t>(g_base);
    if (offset < 0x2C0A000 || offset >= 0x334B000) return nullptr;
    return model;
}

bool Apply(float factor) {
    void* native = PlayerNative();
    float* scale = ScaleSource(native);
    float currentScale = 0, outputScale = 0;
    if (!scale || !Read(scale, currentScale)
            || !g_sourceScale.Update(reinterpret_cast<uintptr_t>(native), currentScale, factor, outputScale)) {
        g_last = "Unit source-scale getter is not supported; see the runtime log"; return false;
    }
    void* model = PlayerModel();
    // Keep the baseline through temporary invisibility; never dereference the cached pointer.
    if (!model) { g_last = "Player render model is not available"; return false; }
    SpatialSize::Matrix current{};
    if (!Read(static_cast<unsigned char*>(model) + 0x100, current) || !SpatialSize::Valid(current)) {
        g_last = "Player spatial transform is unsupported"; return false;
    }
    if (outputScale != currentScale) {
        SIZE_T written = 0;
        if (!WriteProcessMemory(GetCurrentProcess(), scale, &outputScale, sizeof(outputScale), &written) || written != sizeof(outputScale)) {
            g_last = "Unit source scale is not writable"; return false;
        }
        float readback = 0;
        if (!Read(scale, readback) || readback != outputScale) {
            g_last = "Unit source scale readback failed"; return false;
        }
    }
    SpatialSize::Matrix output = g_spatial.Update(reinterpret_cast<uintptr_t>(model), current, factor);
    if (std::memcmp(&current, &output, sizeof(output)))
        Api<void(*)(void*, const SpatialSize::Matrix*)>(0x13863D0)(model, &output);
    SpatialSize::Matrix applied{};
    if (!Read(static_cast<unsigned char*>(model) + 0x100, applied) || std::memcmp(&applied, &output, sizeof(output))) {
        g_last = "Engine did not accept the spatial transform"; return false;
    }
    static float loggedFactor = 1;
    if (factor != loggedFactor) {
        char detail[256]{};
        sprintf_s(detail, "Spatial size factor %.3f applied; first basis=(%.4f,%.4f,%.4f).",
                  factor, output.m[0][0], output.m[0][1], output.m[0][2]);
        Log(detail); loggedFactor = factor;
    }
    g_last = "Local player spatial transform applied";
    return true;
}

int Status(Lua* lua) {
    PushNumber(lua, 2); PushString(lua, "Spatial size; local player, client-side"); PushString(lua, g_last);
    return 3;
}
int Backend(Lua* lua) { PushNumber(lua, 3); return 1; }
int SetSize(Lua* lua) {
    bool valid = Top(lua) == 1 && Type(lua, 1) == 3;
    double factor = valid ? Number(lua, 1) : 1;
    bool ok = valid && BodySize::ValidFactor(factor) && Apply(static_cast<float>(factor));
    PushBool(lua, ok); PushString(lua, valid ? g_last : "Expected one numeric size factor");
    return 2;
}
int Reset(Lua* lua) { bool ok = Apply(1); PushBool(lua, ok); return 1; }

void Register(Lua* lua) {
    uintptr_t stackTop = 0, stackBase = 0;
    if (!Read(reinterpret_cast<unsigned char*>(lua) + 0x28, stackTop)
            || !Read(reinterpret_cast<unsigned char*>(lua) + 0x30, stackBase)
            || stackTop < stackBase || (stackTop - stackBase) % 24 || stackTop - stackBase > 24 * 8000) {
        Log("Bridge refused invalid Lua stack bounds."); return;
    }
    int top = Top(lua);
    if (top != static_cast<int>((stackTop - stackBase) / 24)) { Log("Bridge refused Lua stack ABI mismatch."); return; }
    PushString(lua, "C_BodySliderSL");
    Api<void(*)(Lua*, int)>(0x2C7030)(lua, -10002); // lua_gettable(LUA_GLOBALSINDEX).
    bool exists = Type(lua, -1) == 5;
    if (exists) {
        PushString(lua, "Backend");
        Api<void(*)(Lua*, int)>(0x2C7030)(lua, -2);
        exists = Type(lua, -1) == 6 && Pcall(lua, 0, 1, 0) == 0
            && Type(lua, -1) == 3 && Number(lua, -1) == 3;
    }
    SetTop(lua, top);
    if (exists) return;
    PushString(lua, "C_BodySliderSL");
    Api<void(*)(Lua*, int, int)>(0x2C5CF0)(lua, 0, 4);
    const struct { const char* name; Function function; } entries[] = {
        {"Status", Status}, {"SetSize", SetSize}, {"Reset", Reset}, {"Backend", Backend},
    };
    for (const auto& entry : entries) {
        PushString(lua, entry.name);
        Api<void(*)(Lua*, Function, int)>(0x2C6B60)(lua, entry.function, 0);
        SetTable(lua, -3);
    }
    SetTable(lua, -10002);
    SetTop(lua, top);
    InterlockedExchange(&g_status, 2);
    Log("C_BodySliderSL registered on the game window thread; Overall size native API available.");
}

LRESULT CALLBACK MessageHook(int code, WPARAM removed, LPARAM pointer) {
    if (code == HC_ACTION && removed == PM_REMOVE) {
        auto* message = reinterpret_cast<MSG*>(pointer);
        if (message->message == g_message) {
            // This engine predicate compares the current thread ID with the Lua owner.
            if (Api<bool(*)()>(0x5FD640)()) {
                Lua* lua = State();
                if (lua) Register(lua);
            } else if (!g_threadReported) {
                Log("Bridge deferred: game window thread is not the Lua owner."); g_threadReported = true;
            }
            message->message = WM_NULL;
        }
    }
    return CallNextHookEx(g_hook, code, removed, pointer);
}

BOOL CALLBACK FindWindow(HWND window, LPARAM) {
    DWORD pid = 0; GetWindowThreadProcessId(window, &pid);
    if (pid == GetCurrentProcessId() && IsWindowVisible(window) && !GetWindow(window, GW_OWNER)) {
        wchar_t name[128]{}; GetClassNameW(window, name, 128);
        if (wcscmp(name, L"GxWindowClass") == 0) { g_window = window; return FALSE; }
    }
    return TRUE;
}

bool Initialize(HMODULE owner) {
    g_base = reinterpret_cast<unsigned char*>(GetModuleHandleW(nullptr));
    HMODULE epsilon = GetModuleHandleW(L"EpsilonAddon.dll");
    wchar_t path[32768]{}; char hash[65]{};
    if (!epsilon || !GetModuleFileNameW(epsilon, path, 32768) || !FileDigest(path, hash)
            || std::strcmp(hash, "b3fba2a4059212bebc11c9bcc104b1b008c236cf156ab89014386748cd299fb8") != 0) {
        Log("Runtime disabled: EpsilonAddon identity not recognized."); return false;
    }
    // Existing Epsilon Lua pointers corroborate the engine API bindings. Do not change its validator patches.
    for (const auto& pair : {std::pair<uintptr_t, uintptr_t>{0x2FA470, 0x2C6B60},
            {0x2FA478, 0x2C6E00}, {0x2FA4F8, 0x2C7840}, {0x2FA550, 0x2C71A0},
            {0x2FA558, 0x2C7030}, {0x2FA590, 0x2C7CD0}, {0x2FA5B0, 0x2C5CF0},
            {0x2FA520, 0x2C63E0}}) {
        uintptr_t value = 0;
        if (!Read(reinterpret_cast<unsigned char*>(epsilon) + pair.first, value)
                || value != reinterpret_cast<uintptr_t>(g_base) + pair.second) {
            char detail[256]{};
            sprintf_s(detail, "Runtime disabled: Epsilon Lua slot 0x%llX points to 0x%llX; expected game RVA 0x%llX.",
                      static_cast<unsigned long long>(pair.first), static_cast<unsigned long long>(value),
                      static_cast<unsigned long long>(pair.second));
            Log(detail); return false;
        }
    }
    if (std::memcmp(g_base + 0x2C63E0, "\x48\x8B\x51\x28\x48\xB8\xAB\xAA\xAA\xAA\xAA\xAA\xAA\x2A\x48\x2B\x51\x30", 18) != 0
            || std::memcmp(g_base + 0x5FCC40, "\x48\x8B\x05\x79\0\xF2\x02\xC3", 8) != 0
            || std::memcmp(g_base + 0x206F1B0, "\x48\x83\xEC\x48\x45\x33\xC9\xC6\x44\x24\x20\0\x4C\x8D\x44\x24", 16) != 0
            || std::memcmp(g_base + 0x13863D0, "\xE9\xAB\xB1\xE8\xFF", 5) != 0
            || std::memcmp(g_base + 0x18329B0, "\x48\x8B\x41\x20\x48\x85\xC0\x74\x05\x48\x8B\x40\x28\xC3", 14) != 0) {
        Log("Runtime disabled: render-model ABI bytes differ."); return false;
    }
    g_message = RegisterWindowMessageW(L"BodySliderShadowlands.Register.v1");
    EnumWindows(FindWindow, 0);
    if (!g_message || !g_window) { Log("Runtime disabled: game window not found."); return false; }
    DWORD thread = GetWindowThreadProcessId(g_window, nullptr);
    g_hook = SetWindowsHookExW(WH_GETMESSAGE, MessageHook, owner, thread);
    if (!g_hook) { Log("Runtime disabled: game-thread message hook failed."); return false; }
    Log("Runtime message hook installed; Lua registration waits for the game thread.");
    return true;
}
}
