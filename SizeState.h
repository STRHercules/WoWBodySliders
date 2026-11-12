#pragma once
#include <cmath>
#include <cstdint>

namespace BodySize {
inline bool ValidFactor(double value) { return std::isfinite(value) && value >= 0.5 && value <= 1.5; }
inline bool ValidScale(float value) { return std::isfinite(value) && value >= 0.001f && value <= 1000.f; }

struct State {
    uintptr_t model = 0;
    float base = 1, applied = 1;
    bool active = false;

    bool Update(uintptr_t target, float current, float factor, float& output) {
        if (!target || !ValidScale(current) || !ValidFactor(factor)) return false;
        // The engine can replace the model or change its scale independently (morphs, auras).
        if (!active || model != target || current != applied) base = current;
        output = factor == 1.f ? base : base * factor;
        if (!ValidScale(output)) return false;
        model = target; applied = output; active = factor != 1.f;
        return true;
    }
    void Forget() { *this = {}; }
};
}
