// Test-only DLL for a disposable, non-login analysis client. Never deploy to Epsilon.
#include <windows.h>
#include <bcrypt.h>
#include <cstdio>
#include <cstring>
#include <string>
#include <utility>
#include <vector>
#include "ClientIdentity.h"
#include "SizeState.h"
#include "TransformSize.h"

namespace {
volatile LONG g_status = 0;
HANDLE g_log = INVALID_HANDLE_VALUE;
void Log(const char* message) {
    DWORD written = 0;
    if (g_log != INVALID_HANDLE_VALUE) {
        WriteFile(g_log, message, static_cast<DWORD>(strlen(message)), &written, nullptr);
        WriteFile(g_log, "\r\n", 2, &written, nullptr); FlushFileBuffers(g_log);
    }
}
#include "RuntimeBridge.h"
LRESULT CALLBACK TestHook(int code, WPARAM removed, LPARAM pointer) {
    static bool seen = false;
    if (!seen) { Log("Test message hook invoked"); seen = true; }
    if (code == HC_ACTION && removed == PM_REMOVE) {
        auto* message = reinterpret_cast<MSG*>(pointer);
        if (message->message == Runtime::g_message) {
            message->message = WM_NULL;
            if (!Runtime::Api<bool(*)()>(0x5FD640)()) { Log("FAIL Lua owner thread"); return CallNextHookEx(nullptr, code, removed, pointer); }
            Runtime::Lua* lua = Runtime::State();
            if (!lua) { Log("FAIL no Lua state"); return CallNextHookEx(nullptr, code, removed, pointer); }
            Log("BEGIN Lua registration self-test");
            int top = Runtime::Top(lua);
            Log("Verified gettop returned");
            Runtime::Register(lua);
            bool ok = Runtime::Top(lua) == top;
            Runtime::PushString(lua, "C_BodySliderSL");
            Runtime::Api<void(*)(Runtime::Lua*, int)>(0x2C7030)(lua, -10002);
            ok = ok && Runtime::Type(lua, -1) == 5;
            Runtime::SetTop(lua, top);
            ok = ok && Runtime::Status(lua) == 3 && Runtime::Top(lua) == top + 3;
            Runtime::SetTop(lua, top);
            Runtime::PushNumber(lua, 2.0); // Invalid size: refuses before any model access.
            ok = ok && Runtime::SetSize(lua) == 2 && Runtime::Top(lua) == top + 3;
            Runtime::SetTop(lua, top);
            Log("Checking no-player model refusal");
            bool noPlayer = Runtime::PlayerModel() == nullptr;
            ok = ok && noPlayer && Runtime::Reset(lua) == 1 && Runtime::Top(lua) == top + 1;
            Runtime::SetTop(lua, top);
            Runtime::PushString(lua, "C_BodySliderSL");
            Runtime::Api<void(*)(Runtime::Lua*)>(0x2C6DC0)(lua); // lua_pushnil.
            Runtime::SetTable(lua, -10002);
            Runtime::SetTop(lua, top);
            Log(ok ? "PASS registration table, stack restoration, scalar results, invalid-argument refusal" : "FAIL stack/registration semantics");
            if (Runtime::g_hook) { UnhookWindowsHookEx(Runtime::g_hook); Runtime::g_hook = nullptr; }
        }
    }
    return CallNextHookEx(nullptr, code, removed, pointer);
}
DWORD WINAPI TestWorker(void* parameter) {
    HMODULE module = static_cast<HMODULE>(parameter);
    wchar_t path[32768]{};
    if (!GetModuleFileNameW(module, path, 32768)) return 0;
    wchar_t* slash = wcsrchr(path, L'\\'); if (!slash) return 0;
    swprintf_s(slash + 1, 32768 - (slash + 1 - path), L"bridge-selftest-%lu.log", GetCurrentProcessId());
    g_log = CreateFileW(path, GENERIC_WRITE, FILE_SHARE_READ, nullptr, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr);
    Runtime::g_base = reinterpret_cast<unsigned char*>(GetModuleHandleW(nullptr));
    for (int i = 0; i < 100 && !Runtime::g_window; ++i) { EnumWindows(Runtime::FindWindow, 0); if (!Runtime::g_window) Sleep(100); }
    if (!Runtime::g_window) { Log("FAIL no game window"); return 0; }
    Runtime::g_message = RegisterWindowMessageW(L"BodySliderShadowlands.IsolatedRegistrationTest.v1");
    Runtime::g_hook = SetWindowsHookExW(WH_GETMESSAGE, TestHook, module, GetWindowThreadProcessId(Runtime::g_window, nullptr));
    if (!Runtime::g_hook) { Log("FAIL could not install test hook"); return 0; }
    Log("Test hook installed");
    for (int i = 0; i < 100 && Runtime::g_hook; ++i) {
        PostMessageW(Runtime::g_window, Runtime::g_message, 0, 0);
        Sleep(200);
    }
    return 0;
}
}
BOOL WINAPI DllMain(HINSTANCE module, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(module);
        HANDLE thread = CreateThread(nullptr, 0, TestWorker, module, 0, nullptr);
        if (thread) CloseHandle(thread);
    }
    return TRUE;
}
