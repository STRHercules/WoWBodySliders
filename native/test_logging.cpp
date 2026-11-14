#include "Logging.h"
#include <cassert>
#include <fstream>
#include <string>
#include <thread>
#include <vector>

std::string Read(const wchar_t* filename) {
    std::ifstream stream(filename, std::ios::binary);
    return {std::istreambuf_iterator<char>(stream), std::istreambuf_iterator<char>()};
}
int wmain(int argc, wchar_t** argv) {
    wchar_t temp[MAX_PATH]{}, directory[MAX_PATH]{};
    assert(GetTempPathW(MAX_PATH, temp));
    assert(GetTempFileNameW(temp, L"bsl", 0, directory));
    assert(DeleteFileW(directory) && CreateDirectoryW(directory, nullptr));
    assert(swprintf_s(Diagnostics::path, L"%s\\BodySlider-\x9b54\x517d.log", directory) > 0);
    assert(swprintf_s(Diagnostics::fallback, L"%s\\fallback.log", directory) > 0);
    SetLastError(ERROR_ACCESS_DENIED);
    Diagnostics::WinError("Simulated hook failure", nullptr);
    assert(GetLastError() == ERROR_ACCESS_DENIED);
    auto text = Read(Diagnostics::path);
    assert(text.find("Z [ERROR] pid=") != std::string::npos);
    assert(text.find("Simulated hook failure address=") != std::string::npos);
    assert(text.find("win32=5") != std::string::npos);
    Diagnostics::Log("WARN", "External model name: bad\r\nforged record");
    assert(Read(Diagnostics::path).find("bad  forged record\r\n") != std::string::npos);
    for (int i = 0; i < 10000; ++i) Diagnostics::Limited(nullptr, "repeat", "WARN", "Repeated skeleton rejection");
    text = Read(Diagnostics::path);
    auto first = text.find("Repeated skeleton rejection");
    assert(first != std::string::npos && text.find("Repeated skeleton rejection", first + 1) == std::string::npos);
    unsigned suppressed = 0;
    bool found = false;
    for (auto& repeat : Diagnostics::repeats) if (repeat.suppressed == 9999) { repeat.next = 0; found = true; }
    assert(found && Diagnostics::Allow(nullptr, "repeat", suppressed) && suppressed == 9999);
    std::vector<std::thread> threads;
    for (int i = 0; i < 4; ++i) threads.emplace_back([i] {
        for (int j = 0; j < 25; ++j) Diagnostics::Log("INFO", "Thread record %d:%d", i, j);
    });
    for (auto& thread : threads) thread.join();
    text = Read(Diagnostics::path);
    for (int i = 0; i < 4; ++i) for (int j = 0; j < 25; ++j)
        assert(text.find("Thread record " + std::to_string(i) + ":" + std::to_string(j) + "\r\n") != std::string::npos);
    HANDLE file = CreateFileW(Diagnostics::path, GENERIC_WRITE, 0, nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    assert(file != INVALID_HANDLE_VALUE);
    LARGE_INTEGER limit{}; limit.QuadPart = Diagnostics::MaxBytes;
    assert(SetFilePointerEx(file, limit, nullptr, FILE_BEGIN) && SetEndOfFile(file)); CloseHandle(file);
    Diagnostics::Log("INFO", "After rotation");
    assert(Read(Diagnostics::path).find("After rotation") != std::string::npos);
    std::wstring previous = std::wstring(Diagnostics::path) + L".1";
    assert(GetFileAttributesW(previous.c_str()) != INVALID_FILE_ATTRIBUTES);
    assert(DeleteFileW(Diagnostics::path) && DeleteFileW(previous.c_str()));
    assert(swprintf_s(Diagnostics::path, L"%s\\missing\\BodySlider.log", directory) > 0);
    Diagnostics::Log("ERROR", "Fallback record");
    assert(Read(Diagnostics::fallback).find("Fallback record") != std::string::npos);
    assert(DeleteFileW(Diagnostics::fallback) && RemoveDirectoryW(directory));
    assert(argc == 2);
    HMODULE library = LoadLibraryW(argv[1]);
    assert(library && "DLL dependency/link failure");
    auto initialize = reinterpret_cast<BOOL (__cdecl*)()>(GetProcAddress(library, MAKEINTRESOURCEA(1)));
    assert(initialize && "Missing initializer export ordinal 1");
    // A test executable is not WoW: initialization must log and refuse it before installing hooks.
    assert(!initialize());
    assert(FreeLibrary(library));
    std::puts("logging: Unicode path, error code, last-error preservation, sanitizing, throttling, concurrency, rotation, fallback, DLL load/export/refusal passed");
}
