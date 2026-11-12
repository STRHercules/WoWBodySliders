#pragma once
#include <windows.h>
#include <bcrypt.h>
#include <array>
#include <cstdio>
#include <cstring>

inline bool FileDigest(const wchar_t* path, char actual[65]) {
    HANDLE file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                              nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) return false;
    BCRYPT_ALG_HANDLE algorithm = nullptr;
    BCRYPT_HASH_HANDLE hash = nullptr;
    bool ok = BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_SHA256_ALGORITHM, nullptr, 0) >= 0
        && BCryptCreateHash(algorithm, &hash, nullptr, 0, nullptr, 0, 0) >= 0;
    std::array<unsigned char, 65536> bytes{};
    DWORD read = 0;
    while (ok) {
        if (!ReadFile(file, bytes.data(), static_cast<DWORD>(bytes.size()), &read, nullptr)) { ok = false; break; }
        if (!read) break;
        ok = BCryptHashData(hash, bytes.data(), read, 0) >= 0;
    }
    unsigned char digest[32]{};
    if (ok) ok = BCryptFinishHash(hash, digest, sizeof(digest), 0) >= 0;
    for (int i = 0; i < 32; ++i) sprintf_s(actual + i * 2, 3, "%02x", digest[i]);
    if (hash) BCryptDestroyHash(hash);
    if (algorithm) BCryptCloseAlgorithmProvider(algorithm, 0);
    CloseHandle(file);
    return ok;
}

inline bool SupportedClient(const wchar_t* path) {
    char actual[65]{};
    return FileDigest(path, actual)
        && (std::strcmp(actual, "c5083750b1892cf0c3a029295f3298599558a9b25c6d988c3f107b47f1aff199") == 0
            || std::strcmp(actual, "17f0e43c06a2240f52552436c09379290677765d2983380553a9a9c5a7076b14") == 0);
}
