#include "DeformMath.h"
#include <cassert>
#include <cstdio>
#include <fstream>
#include <string>
#include <vector>

int main(int argc, char** argv) {
    if (argc != 2) { std::puts("Pass the generated client fixture directory"); return 1; }
    std::ifstream manifest(std::string(argv[1]) + "/manifest.txt");
    assert(manifest);
    size_t index = 0;
    std::string name;
    while (std::getline(manifest, name)) {
        assert(index < std::size(ClientDeforms::kProfiles));
        const auto& profile = ClientDeforms::kProfiles[index++];
        std::ifstream file(std::string(argv[1]) + "/" + name + ".vertices", std::ios::binary);
        uint32_t count = 0;
        file.read(reinterpret_cast<char*>(&count), 4);
        assert(count && count <= 65535);
        std::vector<Deform::Vertex> vertices(count);
        file.read(reinterpret_cast<char*>(vertices.data()), count * sizeof(Deform::Vertex));
        assert(file);
        // Duplicate geometry shared with a stock profile may correctly select that stock variant.
        const auto* matched = Deform::Find(profile.path, vertices.data(), count);
        if (!matched) {
            std::printf("Mesh did not match: %s fixture=%s profile=%zu count=%u hash=%016llX\n", profile.path, name.c_str(), index-1, count, static_cast<unsigned long long>(Deform::Fingerprint(vertices.data(), count)));
            return 1;
        }
        vertices[0].uv[0] += .125f;
        assert(!Deform::Find(profile.path, vertices.data(), count));
        vertices[0].uv[0] -= .125f;
        for (int slider = 12; slider < 37; ++slider) {
            if (!Deform::HasSlider(profile, slider)) continue;
            unsigned moved = 0;
            for (int sign : {-1, 1}) {
                if (sign < 0 && slider < 14) continue;
                float controls[37]{}; controls[slider] = static_cast<float>(sign);
                for (uint32_t i = 0; i < count; ++i) {
                    Deform::Vertex result;
                    moved += Deform::Apply(result, vertices[i], profile, controls, i) ? 1 : 0;
                    assert(!std::memcmp(vertices[i].weights, result.weights, 8));
                    assert(!std::memcmp(vertices[i].uv, result.uv, 16));
                    for (float value : result.position) assert(std::isfinite(value));
                    for (float value : result.normal) assert(std::isfinite(value));
                }
            }
            if (!moved) {
                std::printf("No movement: %s profile=%zu slider=%d\n", profile.path, index - 1, slider);
                return 1;
            }
        }
    }
    assert(index == std::size(ClientDeforms::kProfiles));
    std::printf("%zu client meshes: verified matching, tamper rejection, all supported controls move vertices, finite results, UV/weights preserved\n", index);
}
