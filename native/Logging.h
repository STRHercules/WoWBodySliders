#pragma once
#include <windows.h>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <cwchar>
#include <cstdint>
#include <iterator>

namespace Diagnostics {
inline SRWLOCK lock = SRWLOCK_INIT;
inline wchar_t path[32768]{}, fallback[32768]{};
constexpr LONGLONG MaxBytes = 4 * 1024 * 1024;
struct Repeat { unsigned long long key = 0, next = 0; unsigned suppressed = 0; };
inline Repeat repeats[512]{};

inline void Paths() {
    DWORD length = GetModuleFileNameW(nullptr, path, static_cast<DWORD>(std::size(path)));
    if (length && length < std::size(path)) {
        wchar_t* slash = std::wcsrchr(path, L'\\');
        if (!slash || wcscpy_s(slash + 1, std::size(path) - (slash + 1 - path), L"BodySlider.log")) path[0] = 0;
    } else path[0] = 0;
    DWORD size = GetEnvironmentVariableW(L"LOCALAPPDATA", fallback, static_cast<DWORD>(std::size(fallback)));
    if (!size || size >= std::size(fallback) || wcscat_s(fallback, L"\\BodySlider")) { fallback[0] = 0; return; }
    CreateDirectoryW(fallback, nullptr);
    if (wcscat_s(fallback, L"\\BodySlider.log")) fallback[0] = 0;
}
inline HANDLE Open(const wchar_t* filename) {
    if (!*filename) return INVALID_HANDLE_VALUE;
    HANDLE file = CreateFileW(filename, FILE_APPEND_DATA | FILE_READ_ATTRIBUTES, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                              nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) return file;
    LARGE_INTEGER size{};
    if (GetFileSizeEx(file, &size) && size.QuadPart >= MaxBytes) {
        CloseHandle(file);
        wchar_t previous[32768]{};
        if (swprintf_s(previous, L"%s.1", filename) < 0 || !MoveFileExW(filename, previous, MOVEFILE_REPLACE_EXISTING))
            return INVALID_HANDLE_VALUE;
        file = CreateFileW(filename, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                           nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    }
    return file;
}
inline void WriteV(const char* level, const char* format, va_list arguments) {
    DWORD savedError = GetLastError();
    char text[2048]{};
    _vsnprintf_s(text, sizeof(text), _TRUNCATE, format, arguments);
    // Keep model paths and external strings from injecting extra log records.
    for (char* c = text; *c; ++c) if (static_cast<unsigned char>(*c) < 32) *c = ' ';
    SYSTEMTIME time{}; GetSystemTime(&time);
    char line[2304]{};
    int length = _snprintf_s(line, sizeof(line), _TRUNCATE,
        "%04u-%02u-%02uT%02u:%02u:%02u.%03uZ [%s] pid=%lu tid=%lu %s\r\n",
        time.wYear, time.wMonth, time.wDay, time.wHour, time.wMinute, time.wSecond, time.wMilliseconds,
        level, GetCurrentProcessId(), GetCurrentThreadId(), text);
    AcquireSRWLockExclusive(&lock);
    if (!path[0] && !fallback[0]) Paths();
    HANDLE file = Open(path);
    if (file == INVALID_HANDLE_VALUE) file = Open(fallback);
    DWORD written = 0;
    bool ok = file != INVALID_HANDLE_VALUE && length > 0
        && WriteFile(file, line, static_cast<DWORD>(length), &written, nullptr) && written == static_cast<DWORD>(length);
    if (file != INVALID_HANDLE_VALUE) {
        if (std::strcmp(level, "ERROR") == 0) FlushFileBuffers(file);
        CloseHandle(file);
    }
    if (!ok) { OutputDebugStringA("BodySlider log write failed: "); OutputDebugStringA(line); }
    ReleaseSRWLockExclusive(&lock);
    SetLastError(savedError);
}
inline void Log(const char* level, const char* format, ...) {
    va_list arguments; va_start(arguments, format); WriteV(level, format, arguments); va_end(arguments);
}
inline void WinError(const char* operation, const void* address = nullptr) {
    DWORD error = GetLastError();
    char description[512]{};
    FormatMessageA(FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS, nullptr, error, 0,
                   description, sizeof(description), nullptr);
    Log("ERROR", "%s address=%p win32=%lu (%s)", operation, address, error, description);
    SetLastError(error);
}
inline bool Allow(const void* object, const char* category, unsigned& suppressed) {
    unsigned long long key = 14695981039346656037ull;
    for (const char* c = category; *c; ++c) key = (key ^ static_cast<unsigned char>(*c)) * 1099511628211ull;
    key ^= reinterpret_cast<uintptr_t>(object);
    if (!key) key = 1;
    ULONGLONG now = GetTickCount64();
    AcquireSRWLockExclusive(&lock);
    Repeat* available = nullptr;
    for (size_t i = 0; i < std::size(repeats); ++i) {
        auto& repeat = repeats[(key + i) % std::size(repeats)];
        if (repeat.key == key) {
            if (repeat.key == key && repeat.next > now) {
                if (repeat.suppressed != ~0u) ++repeat.suppressed;
                ReleaseSRWLockExclusive(&lock); return false;
            }
            suppressed = repeat.key == key ? repeat.suppressed : 0;
            repeat = {key, now + 60000, 0};
            ReleaseSRWLockExclusive(&lock); return true;
        }
        if ((!repeat.key || repeat.next <= now) && !available) available = &repeat;
        if (!repeat.key) break;
    }
    if (available) {
        *available = {key, now + 60000, 0}; suppressed = 0;
        ReleaseSRWLockExclusive(&lock); return true;
    }
    ReleaseSRWLockExclusive(&lock); return false;
}
inline void Limited(const void* object, const char* category, const char* level, const char* format, ...) {
    DWORD savedError = GetLastError();
    unsigned suppressed = 0;
    if (Allow(object, category, suppressed)) {
        if (suppressed) Log("INFO", "%s object=%p suppressed=%u repeats in previous minute", category, object, suppressed);
        va_list arguments; va_start(arguments, format); WriteV(level, format, arguments); va_end(arguments);
    }
    SetLastError(savedError);
}
}
