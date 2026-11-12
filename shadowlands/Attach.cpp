#include <windows.h>
#include <tlhelp32.h>
#include <cstdio>
#include <cstring>
#include <string>
#include <io.h>
#include "ClientIdentity.h"

namespace {
DWORD g_target = 0;
uintptr_t ModuleBase(DWORD pid, const wchar_t* name) {
    HANDLE snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid);
    if (snapshot == INVALID_HANDLE_VALUE) return 0;
    MODULEENTRY32W entry{};
    entry.dwSize = sizeof(entry);
    uintptr_t result = 0;
    if (Module32FirstW(snapshot, &entry)) {
        do {
            if (!name || _wcsicmp(entry.szModule, name) == 0) {
                result = reinterpret_cast<uintptr_t>(entry.modBaseAddr);
                break;
            }
        } while (Module32NextW(snapshot, &entry));
    }
    CloseHandle(snapshot);
    return result;
}

bool Inject(HANDLE process, DWORD pid, const std::wstring& path) {
    auto load = GetProcAddress(GetModuleHandleW(L"kernel32.dll"), "LoadLibraryW");
    HMODULE owner = nullptr;
    if (!load || !GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                                     reinterpret_cast<LPCWSTR>(load), &owner)) return false;
    wchar_t name[32768]{};
    if (!GetModuleFileNameW(owner, name, 32768)) return false;
    const wchar_t* basename = wcsrchr(name, L'\\');
    if (!basename) return false;
    uintptr_t remote = ModuleBase(pid, basename + 1);
    if (!remote) return false;
    auto remoteLoad = reinterpret_cast<LPTHREAD_START_ROUTINE>(remote + reinterpret_cast<uintptr_t>(load)
                                                              - reinterpret_cast<uintptr_t>(owner));
    SIZE_T size = (path.size() + 1) * sizeof(wchar_t);
    void* buffer = VirtualAllocEx(process, nullptr, size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (!buffer) return false;
    SIZE_T written = 0;
    bool ok = WriteProcessMemory(process, buffer, path.c_str(), size, &written) && written == size;
    HANDLE thread = ok ? CreateRemoteThread(process, nullptr, 0, remoteLoad, buffer, 0, nullptr) : nullptr;
    bool finished = thread && WaitForSingleObject(thread, 30000) == WAIT_OBJECT_0;
    // A timed-out loader may still use the path; leave that allocation to process teardown.
    if (!thread || finished) VirtualFreeEx(process, buffer, 0, MEM_RELEASE);
    if (thread) CloseHandle(thread);
    return finished && ModuleBase(pid, L"BodySliderShadowlandsRuntime-0.2.4.dll") != 0;
}
}

int Run(int argc, wchar_t** argv) {
    wchar_t self[32768]{};
    DWORD length = GetModuleFileNameW(nullptr, self, 32768);
    if (!length || length >= 32768) return 1;
    std::wstring directory(self, length);
    size_t slash = directory.find_last_of(L"\\/");
    if (slash == std::wstring::npos) return 1;
    directory.resize(slash + 1);
    std::wstring original = directory + L"Wow.exe", dll = directory + L"BodySliderShadowlandsRuntime-0.2.4.dll";
    if (GetFileAttributesW(original.c_str()) == INVALID_FILE_ATTRIBUTES || GetFileAttributesW(dll.c_str()) == INVALID_FILE_ATTRIBUTES) {
        fwprintf(stderr, L"Missing sibling Wow.exe or BodySliderShadowlandsRuntime-0.2.4.dll.\n");
        return 2;
    }
    if (!SupportedClient(original.c_str())) {
        fwprintf(stderr, L"Unsupported Wow.exe SHA-256; expected supplied 9.2.7.45745. Nothing launched.\n");
        return 5;
    }
    DWORD selected = 0;
    if (argc > 2) { fwprintf(stderr, L"Usage: BodySliderShadowlandsAttach.exe [PID]\n"); return 6; }
    if (argc == 2) {
        wchar_t* end = nullptr;
        unsigned long parsed = wcstoul(argv[1], &end, 10);
        if (!parsed || !end || *end) { fwprintf(stderr, L"Invalid PID.\n"); return 6; }
        selected = parsed;
    }
    HANDLE snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (snapshot == INVALID_HANDLE_VALUE) return 7;
    PROCESSENTRY32W entry{}; entry.dwSize = sizeof(entry);
    DWORD target = 0, count = 0;
    if (Process32FirstW(snapshot, &entry)) do {
        if (_wcsicmp(entry.szExeFile, L"Wow.exe") != 0 || (selected && selected != entry.th32ProcessID)) continue;
        HANDLE query = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, entry.th32ProcessID);
        if (!query) continue;
        wchar_t path[32768]{}; DWORD size = 32768;
        bool match = QueryFullProcessImageNameW(query, 0, path, &size) && _wcsicmp(path, original.c_str()) == 0;
        CloseHandle(query);
        if (match) { target = entry.th32ProcessID; ++count; printf("Matching Epsilon client PID %lu\n", target); }
    } while (Process32NextW(snapshot, &entry));
    CloseHandle(snapshot);
    if (count != 1) {
        fwprintf(stderr, L"Expected one running client from this folder. Start it through Epsilon first; supply a PID if several are running.\n");
        return 8;
    }
    HANDLE process = OpenProcess(PROCESS_CREATE_THREAD | PROCESS_VM_OPERATION | PROCESS_VM_READ | PROCESS_VM_WRITE
                                 | PROCESS_QUERY_INFORMATION | SYNCHRONIZE, FALSE, target);
    g_target = target;
    if (!process) {
        fwprintf(stderr, L"OpenProcess failed: %lu. Run this helper at the same elevation as Epsilon (Run as administrator if Epsilon is elevated). No client changed.\n", GetLastError());
        return 9;
    }
    if (!ModuleBase(target, L"EpsilonAddon.dll")) {
        fwprintf(stderr, L"EpsilonAddon.dll was not observed. Wait for Epsilon initialization; no DLL was loaded.\n");
        CloseHandle(process);
        return 10;
    }
    printf("EpsilonAddon.dll verified; preserving the existing Epsilon-launched process.\n");
    bool loaded = ModuleBase(target, L"BodySliderShadowlandsRuntime-0.2.4.dll") != 0 || Inject(process, target, dll);
    printf("Runtime DLL module load: %s. Check /bodyslider for native bridge and overall-size status.\n", loaded ? "verified" : "not verified");
    if (!loaded) printf("Win32 error: %lu. Original client remains unmodified.\n", GetLastError());
    CloseHandle(process);
    return loaded ? 0 : 4;
}

int wmain(int argc, wchar_t** argv) {
    int result = Run(argc, argv);
    const char* message = "Attach failed; see the console output.";
    switch (result) {
        case 0: message = "Runtime DLL module load verified. Overall-size prototype; check /bodyslider for bridge readiness. Bone/mesh proportions are not implemented."; break;
        case 2: message = "Missing sibling Wow.exe or BodySliderShadowlandsRuntime-0.2.4.dll."; break;
        case 4: message = "DLL module load was not verified. No slider functionality is available."; break;
        case 5: message = "Unsupported executable SHA-256. Nothing attached."; break;
        case 6: message = "Invalid arguments. Usage: BodySliderShadowlandsAttach.exe [PID]"; break;
        case 7: message = "Could not enumerate processes."; break;
        case 8: message = "No unique matching client. Launch through Epsilon first; pass a PID if several clients are running."; break;
        case 9: message = "Windows denied process access. Run this helper as administrator if Epsilon is elevated. Nothing attached."; break;
        case 10: message = "EpsilonAddon.dll was not observed. Wait for Epsilon initialization. Nothing attached."; break;
    }
    printf("\nResult %d: %s\n", result, message);
    wchar_t path[32768]{};
    DWORD length = GetModuleFileNameW(nullptr, path, 32768);
    if (length && length < 32768) {
        wchar_t* slash = wcsrchr(path, L'\\');
        if (slash && static_cast<size_t>(slash - path) + 40 < 32768) {
            wcscpy_s(slash + 1, 32768 - (slash + 1 - path), L"BodySliderShadowlandsAttach.log");
            HANDLE log = CreateFileW(path, FILE_APPEND_DATA, FILE_SHARE_READ, nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
            if (log != INVALID_HANDLE_VALUE) {
                SYSTEMTIME now{}; GetSystemTime(&now);
                char line[1024]{};
                int size = sprintf_s(line, "%04u-%02u-%02uT%02u:%02u:%02uZ target_pid=%lu result=%d %s\r\n",
                                     now.wYear, now.wMonth, now.wDay, now.wHour, now.wMinute, now.wSecond,
                                     g_target, result, message);
                DWORD written = 0;
                if (size > 0) WriteFile(log, line, size, &written, nullptr);
                CloseHandle(log);
            } else fwprintf(stderr, L"Could not write attach result log: %lu\n", GetLastError());
        }
    }
    DWORD processes[2]{};
    if (_isatty(_fileno(stdin)) && GetConsoleProcessList(processes, 2) == 1) {
        printf("\nPress Enter to close this window.\n");
        fflush(stdout); fflush(stderr);
        (void)getchar();
    }
    return result;
}
