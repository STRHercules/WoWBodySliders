#include <windows.h>
#include <bcrypt.h>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
#include <utility>
#include "SizeState.h"
#include "TransformSize.h"
#include "ClientProfile.h"
#include "ClientIdentity.h"

namespace {
HANDLE g_log = INVALID_HANDLE_VALUE;
volatile LONG g_status = 0;

void Log(const char* text) {
    if (g_log == INVALID_HANDLE_VALUE) return;
    DWORD written = 0;
    WriteFile(g_log, text, static_cast<DWORD>(std::strlen(text)), &written, nullptr);
    WriteFile(g_log, "\r\n", 2, &written, nullptr);
    FlushFileBuffers(g_log);
}

#include "RuntimeBridge.h"

DWORD WINAPI Worker(void*) try {
    // Pin before returning from DllMain's worker: executable imports already retain us.
    HMODULE pinned = nullptr;
    if (!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_PIN,
                           reinterpret_cast<LPCWSTR>(&Worker), &pinned)) return 0;
    wchar_t executable[32768]{};
    DWORD length = GetModuleFileNameW(nullptr, executable, 32768);
    if (!length || length >= 32768) return 0;
    std::wstring directory(executable, length);
    size_t slash = directory.find_last_of(L"\\/");
    if (slash == std::wstring::npos) return 0;
    directory.resize(slash + 1);
    SYSTEMTIME now{};
    GetSystemTime(&now);
    wchar_t stem[128]{};
    swprintf_s(stem, L"BodySliderShadowlandsRuntime-%lu-%04u%02u%02uT%02u%02u%02u", GetCurrentProcessId(),
               now.wYear, now.wMonth, now.wDay, now.wHour, now.wMinute, now.wSecond);
    std::wstring prefix = directory + stem;
    g_log = CreateFileW((prefix + L".log").c_str(), GENERIC_WRITE, FILE_SHARE_READ, nullptr,
                        CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (g_log == INVALID_HANDLE_VALUE) { InterlockedExchange(&g_status, -2); return 0; }
    Log("BodySlider Shadowlands 0.2.4 runtime loaded; verified-getter source-scale prototype. Bone/mesh proportions are not implemented.");
    if (!SupportedClient(executable)) {
        Log("Unsupported executable code fingerprint: diagnostics disabled.");
        InterlockedExchange(&g_status, -1);
        CloseHandle(g_log); g_log = INVALID_HANDLE_VALUE;
        return 0;
    }
    Log("On-disk x64 9.2.7.45745 full executable SHA-256 matched. This is not hook/ABI validation.");
    InterlockedExchange(&g_status, 1);
    bool runtime = Runtime::Initialize(pinned);
    auto* base = reinterpret_cast<unsigned char*>(GetModuleHandleW(nullptr));
    for (int attempt = 0; attempt <= 60; ++attempt) {
        if (runtime) PostMessageW(Runtime::g_window, Runtime::g_message, 0, 0);
        if (attempt == 0 || attempt == 5 || attempt == 15 || attempt == 60) {
            for (const auto& range : CodeRanges) {
                std::vector<unsigned char> bytes(range.size);
                SIZE_T read = 0;
                bool ok = ReadProcessMemory(GetCurrentProcess(), base + range.rva, bytes.data(), bytes.size(), &read)
                    && read == bytes.size();
                char message[512]{};
                bool changed = ok && std::memcmp(bytes.data(), range.disk, sizeof(range.disk)) != 0;
                sprintf_s(message, "t=%ds %s RVA=0x%X size=0x%X readable=%d differs_from_disk=%d", attempt,
                          range.name, range.rva, range.size, ok, changed);
                Log(message);
                if (!ok) continue;
                wchar_t suffix[128]{};
                swprintf_s(suffix, L"-%02ds-%08X.bin", attempt, range.rva);
                HANDLE output = CreateFileW((prefix + suffix).c_str(), GENERIC_WRITE, FILE_SHARE_READ,
                                            nullptr, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr);
                if (output == INVALID_HANDLE_VALUE) { Log("Code sample creation failed."); continue; }
                DWORD written = 0;
                if (!WriteFile(output, bytes.data(), static_cast<DWORD>(bytes.size()), &written, nullptr)
                        || written != bytes.size()) Log("Code sample write failed; sample is incomplete.");
                CloseHandle(output);
            }
        }
        if (attempt < 60) Sleep(1000);
    }
    Log("Code capture complete. Runtime bridge polling continues for UI reloads.");
    while (runtime && IsWindow(Runtime::g_window)) {
        if (!PostMessageW(Runtime::g_window, Runtime::g_message, 0, 0)) break;
        Sleep(1000);
    }
    CloseHandle(g_log); g_log = INVALID_HANDLE_VALUE;
    return 0;
} catch (...) {
    Log("Diagnostic worker failed; no engine hooks were installed.");
    if (g_log != INVALID_HANDLE_VALUE) { CloseHandle(g_log); g_log = INVALID_HANDLE_VALUE; }
    InterlockedExchange(&g_status, -4);
    return 0;
}
}

extern "C" __declspec(dllexport) int BodySlider_Bootstrap() {
    return 1; // Import anchor only; no engine calls or loader-lock waits.
}
extern "C" __declspec(dllexport) LONG BodySlider_DiagnosticsStatus() {
    return InterlockedCompareExchange(&g_status, 0, 0);
}
BOOL WINAPI DllMain(HINSTANCE module, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(module);
        // New thread execution is serialized behind DLL initialization; never wait here.
        HANDLE thread = CreateThread(nullptr, 0, Worker, nullptr, 0, nullptr);
        if (thread) CloseHandle(thread);
        else InterlockedExchange(&g_status, -3);
    }
    return TRUE;
}
