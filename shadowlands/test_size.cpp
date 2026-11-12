#include "SizeState.h"
#include <cassert>
#include <limits>

int main() {
    BodySize::State state;
    float output = 0;
    assert(state.Update(10, 2, 1.25f, output) && output == 2.5f);
    assert(state.Update(10, 2.5f, 1.25f, output) && output == 2.5f); // No cumulative scaling.
    assert(state.Update(10, 2.5f, 0.5f, output) && output == 1.f);
    assert(state.Update(10, 1.f, 1.f, output) && output == 2.f && !state.active);
    assert(state.Update(10, 2.f, 1.5f, output) && output == 3.f);
    assert(state.Update(10, 4.f, 1.5f, output) && output == 6.f); // External scale becomes the new baseline.
    assert(state.Update(10, 6.f, 1.f, output) && output == 4.f);
    assert(state.Update(11, 0.8f, 1.5f, output) && std::fabs(output - 1.2f) < 1e-6f);
    assert(state.Update(12, 1.f, 1.f, output) && output == 1.f); // Never restore another model's baseline.
    assert(!state.Update(0, 1.f, 1.f, output));
    assert(!state.Update(12, 1.f, 1.6f, output));
    assert(!state.Update(12, -1.f, 1.f, output));
    assert(!BodySize::ValidFactor(std::numeric_limits<double>::quiet_NaN()));
    assert(!BodySize::ValidScale(std::numeric_limits<float>::infinity()));
    return 0;
}
