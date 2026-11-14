#pragma once
#include <algorithm>
#include <string>
#include <vector>
#include <stdexcept>

namespace DynamicPatch {
using Bytes = std::vector<unsigned char>;
struct Image {
    Bytes& data;
    DWORD pe, optional, sections, count, headers, next = 0;
    DWORD get(DWORD at, DWORD size = 4) const {
        if (at > data.size() || size > data.size() - at) throw std::runtime_error("Truncated PE data");
        DWORD value = 0;
        std::memcpy(&value, data.data() + at, size);
        return value;
    }
    void put(DWORD at, DWORD value, DWORD size = 4) {
        get(at, size);
        std::memcpy(data.data() + at, &value, size);
    }
    DWORD offset(DWORD rva, DWORD size) const {
        for (DWORD i = 0; i < count; ++i) {
            DWORD section = sections + i * 40, address = get(section + 12), length = get(section + 16);
            if (rva >= address && rva - address <= length && size <= length - (rva - address))
                return get(section + 20) + rva - address;
        }
        throw std::runtime_error("Invalid PE data RVA");
    }
    explicit Image(Bytes& bytes) : data(bytes) {
        if (get(0, 2) != 0x5a4d) throw std::runtime_error("Not a PE executable");
        pe = get(0x3c);
        if (get(pe) != 0x4550 || get(pe + 4, 2) != 0x14c || get(pe + 20, 2) < 224)
            throw std::runtime_error("Expected x86 PE32 executable");
        optional = pe + 24; count = get(pe + 6, 2); sections = optional + get(pe + 20, 2);
        headers = get(optional + 60);
        if (!count || get(optional, 2) != 0x10b || get(optional + 28) != 0x400000
                || (get(optional + 70, 2) & 0x40)
                || get(optional + 32) != 0x1000 || get(optional + 36) != 0x200
                || headers > data.size() || sections + count * 40 > headers)
            throw std::runtime_error("Incompatible PE layout or insufficient section-header space");
        for (DWORD i = 0; i < count; ++i) {
            DWORD s = sections + i * 40, raw = get(s + 20), size = get(s + 16);
            if (raw > data.size() || size > data.size() - raw) throw std::runtime_error("Truncated section");
            uint64_t end = uint64_t(get(s + 12)) + std::max(get(s + 8), size);
            if (end > 0xffffe000) throw std::runtime_error("PE image too large");
            next = std::max(next, (DWORD(end) + 4095) & ~4095u);
        }
    }
    DWORD resourceEntry(DWORD base, DWORD length, DWORD relative, DWORD wanted = 0xffffffff) const {
        if (relative > length || length - relative < 16) throw std::runtime_error("Invalid resource directory");
        DWORD countEntries = get(base + relative + 12, 2) + get(base + relative + 14, 2);
        for (DWORD i = 0; i < countEntries; ++i) {
            DWORD at = relative + 16 + i * 8;
            if (at > length || length - at < 8) throw std::runtime_error("Truncated resource directory");
            if (wanted == 0xffffffff || get(base + at) == wanted) return get(base + at + 4);
        }
        throw std::runtime_error("Missing executable version resource");
    }
    void version() const {
        DWORD length = get(optional + 116), base = offset(get(optional + 112), length);
        DWORD target = resourceEntry(base, length, 0, 16);
        for (int i = 0; i < 2; ++i) {
            if (!(target & 0x80000000)) throw std::runtime_error("Invalid version resource tree");
            target = resourceEntry(base, length, target & 0x7fffffff);
        }
        if ((target & 0x80000000) || target > length || length - target < 16)
            throw std::runtime_error("Invalid version resource");
        DWORD size = get(base + target + 4), at = offset(get(base + target), size);
        static const wchar_t key[] = L"VS_VERSION_INFO";
        get(at + size - 1, 1);
        if (size < 92 || std::memcmp(data.data() + at + 6, key, sizeof(key))
                || get(at + 40) != 0xfeef04bd || get(at + 44) != 0x10000
                || get(at + 48) != 0x30003 || get(at + 52) != ((5 << 16) | 12340))
            throw std::runtime_error("Expected WoW version 3.3.5.12340");
    }
    DWORD import(const char* function) const {
        DWORD length = get(optional + 108), base = offset(get(optional + 104), length);
        for (DWORD i = 0; i + 20 <= length; i += 20) {
            DWORD descriptor = base + i, name = get(descriptor + 12);
            if (!name) break;
            DWORD at = offset(name, 13); get(at + 12, 1);
            if (_strnicmp(reinterpret_cast<const char*>(data.data() + at), "kernel32.dll", 13)) continue;
            DWORD lookup = get(descriptor), iat = get(descriptor + 16);
            for (DWORD j = 0; j < data.size() / 4; ++j) {
                DWORD thunk = get(offset((lookup ? lookup : iat) + j * 4, 4));
                if (!thunk) break;
                if (thunk & 0x80000000) continue;
                DWORD nameAt = offset(thunk + 2, static_cast<DWORD>(std::strlen(function) + 1));
                get(nameAt + static_cast<DWORD>(std::strlen(function)), 1);
                if (!std::strcmp(reinterpret_cast<const char*>(data.data() + nameAt), function)) {
                    get(offset(iat + j * 4, 4));
                    return 0x400000 + iat + j * 4;
                }
            }
        }
        throw std::runtime_error("Missing required KERNEL32 loader import");
    }
};
inline std::string digest(const Bytes& bytes) {
    unsigned char hash[32]{};
    if (!Hash(bytes.data(), static_cast<DWORD>(bytes.size()), hash)) throw std::runtime_error("SHA-256 failed");
    std::string result;
    for (auto value : hash) { result += "0123456789abcdef"[value >> 4]; result += "0123456789abcdef"[value & 15]; }
    return result;
}
inline DWORD checksum(const Bytes& data, DWORD at) {
    DWORD sum = 0;
    for (DWORD i = 0; i < data.size(); i += 2) {
        if (i < at || i >= at + 4) sum += data[i] | (i + 1 < data.size() ? data[i + 1] << 8 : 0);
        sum = (sum & 0xffff) + (sum >> 16);
    }
    return (sum & 0xffff) + (sum >> 16) + static_cast<DWORD>(data.size());
}
inline bool marked(const Bytes& bytes) {
    static const char marker[] = "BodySliderPatch1";
    return bytes.size() >= sizeof(marker) && !std::memcmp(bytes.data() + bytes.size() - sizeof(marker), marker, sizeof(marker));
}
inline Bytes patch(Bytes original) {
    Image image(original);
    if (image.sections + (image.count + 1) * 40 > image.headers)
        throw std::runtime_error("Insufficient section-header space");
    for (DWORD i = 0; i < image.count; ++i)
        if (!std::memcmp(original.data() + image.sections + i * 40, ".bslide", 8)) throw std::runtime_error("Executable already patched");
    image.version();
    DWORD filename = image.import("GetModuleFileNameA"), library = image.import("LoadLibraryA");
    Bytes output = original;
    DWORD raw = (static_cast<DWORD>(output.size()) + 511) & ~511u;
    // Reuse only the generated loader code; headers and restoration data belong to this input.
    Bytes stub(PatchData::Stub, PatchData::Stub + sizeof(PatchData::Stub));
    for (DWORD i = 0; i + 4 <= stub.size(); ++i) {
        DWORD value; std::memcpy(&value, stub.data() + i, 4);
        if (value == 0x9df1a0 || value == 0x9df248) {
            value = value == 0x9df1a0 ? filename : library;
            std::memcpy(stub.data() + i, &value, 4); i += 3;
        }
    }
    DWORD jump = image.get(image.optional + 16) - (image.next + static_cast<DWORD>(stub.size()));
    std::memcpy(stub.data() + stub.size() - 4, &jump, 4);
    DWORD rawSize = (static_cast<DWORD>(stub.size()) + 511) & ~511u;
    output.resize(raw + rawSize);
    std::copy(stub.begin(), stub.end(), output.begin() + raw);
    Image out(output);
    DWORD section = image.sections + image.count * 40;
    std::memset(output.data() + section, 0, 40);
    std::memcpy(output.data() + section, ".bslide", 8);
    out.put(section + 8, static_cast<DWORD>(stub.size())); out.put(section + 12, image.next);
    out.put(section + 16, rawSize); out.put(section + 20, raw); out.put(section + 36, 0x60000020);
    out.put(image.pe + 6, image.count + 1, 2);
    out.put(image.optional + 4, image.get(image.optional + 4) + rawSize);
    out.put(image.optional + 16, image.next);
    out.put(image.optional + 56, (image.next + static_cast<DWORD>(stub.size()) + 4095) & ~4095u);
    out.put(image.optional + 128, 0); out.put(image.optional + 132, 0); out.put(image.optional + 64, 0);
    DWORD length = 0;
    if (!CryptBinaryToStringA(original.data(), image.headers, CRYPT_STRING_BASE64 | CRYPT_STRING_NOCRLF, nullptr, &length))
        throw std::runtime_error("Header encoding failed");
    std::string headers(length, '\0');
    if (!CryptBinaryToStringA(original.data(), image.headers, CRYPT_STRING_BASE64 | CRYPT_STRING_NOCRLF, headers.data(), &length))
        throw std::runtime_error("Header encoding failed");
    headers.resize(std::strlen(headers.c_str()));
    std::string metadata = "{\"body_sha256\":\"" + digest(output) + "\",\"original_headers\":\"" + headers
        + "\",\"original_sha256\":\"" + digest(original) + "\",\"original_size\":" + std::to_string(original.size()) + ",\"version\":1}";
    if (metadata.size() > 16384) throw std::runtime_error("Restoration metadata too large");
    output.insert(output.end(), metadata.begin(), metadata.end());
    DWORD size = static_cast<DWORD>(metadata.size());
    const auto* sizeBytes = reinterpret_cast<const unsigned char*>(&size);
    output.insert(output.end(), sizeBytes, sizeBytes + 4);
    static const char marker[] = "BodySliderPatch1";
    output.insert(output.end(), marker, marker + sizeof(marker));
    out.put(image.optional + 64, checksum(output, image.optional + 64));
    return output;
}
inline Bytes restore(Bytes input) {
    if (!marked(input) || input.size() < 21) throw std::runtime_error("Not a BodySlider-patched executable");
    Image image(input);
    DWORD end = static_cast<DWORD>(input.size()) - 21, size = image.get(end);
    if (size > 16384 || size > end) throw std::runtime_error("Invalid restoration metadata length");
    std::string metadata(input.begin() + end - size, input.begin() + end);
    // Accept precisely the canonical metadata written by both patchers, including legacy patches.
    char bodyHash[65]{}, headers[16385]{}, originalHash[65]{};
    unsigned long originalSize = 0;
    int fields = sscanf_s(metadata.c_str(), "{\"body_sha256\":\"%64[0-9a-f]\",\"original_headers\":\"%16384[A-Za-z0-9+/=]\",\"original_sha256\":\"%64[0-9a-f]\",\"original_size\":%lu,\"version\":1}",
        bodyHash, 65u, headers, 16385u, originalHash, 65u, &originalSize);
    std::string canonical = std::string("{\"body_sha256\":\"") + bodyHash + "\",\"original_headers\":\"" + headers
        + "\",\"original_sha256\":\"" + originalHash + "\",\"original_size\":" + std::to_string(originalSize) + ",\"version\":1}";
    if (fields != 4 || canonical != metadata) throw std::runtime_error("Invalid restoration metadata");
    input.resize(end - size); image.put(image.optional + 64, 0);
    if (digest(input) != bodyHash) throw std::runtime_error("Patched executable has changed; refusing restoration");
    DWORD headerSize = image.headers;
    Bytes decoded(headerSize);
    if (!CryptStringToBinaryA(headers, 0, CRYPT_STRING_BASE64, decoded.data(), &headerSize, nullptr, nullptr)
            || headerSize != image.headers || originalSize < headerSize || originalSize > input.size())
        throw std::runtime_error("Invalid restoration bounds");
    input.resize(originalSize); std::copy(decoded.begin(), decoded.end(), input.begin());
    if (digest(input) != originalHash) throw std::runtime_error("Restored executable digest mismatch");
    return input;
}
}
