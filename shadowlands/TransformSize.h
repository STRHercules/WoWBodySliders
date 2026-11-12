#pragma once
#include <cmath>
#include <cstdint>

namespace SpatialSize {
struct Matrix { float m[4][4]; };
inline bool Valid(const Matrix& matrix) {
    for (const auto& row : matrix.m) for (float value : row) if (!std::isfinite(value)) return false;
    for (int row = 0; row < 3; ++row) {
        float length = 0;
        for (int axis = 0; axis < 3; ++axis) length += matrix.m[row][axis] * matrix.m[row][axis];
        if (length < 1e-10f || length > 1e8f) return false;
    }
    return true;
}
inline Matrix Apply(const Matrix& source, float factor) {
    Matrix result = source;
    for (int row = 0; row < 3; ++row) for (int axis = 0; axis < 3; ++axis) result.m[row][axis] *= factor;
    return result;
}
struct State {
    uintptr_t model = 0;
    Matrix applied{};
    float factor = 1;
    Matrix Update(uintptr_t target, const Matrix& current, float desired) {
        bool ours = target == model;
        for (int row = 0; row < 3; ++row) for (int axis = 0; axis < 3; ++axis)
            ours = ours && current.m[row][axis] == applied.m[row][axis];
        Matrix result = Apply(current, ours ? desired / factor : desired);
        model = target; applied = result; factor = desired;
        return result;
    }
};
}
