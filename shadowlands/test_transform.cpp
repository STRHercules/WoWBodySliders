#include "TransformSize.h"
#include <cassert>
#include <limits>
int main() {
    SpatialSize::Matrix matrix{{{0,2,0,0},{-2,0,0,0},{0,0,2,0},{40,50,60,1}}};
    assert(SpatialSize::Valid(matrix));
    SpatialSize::State state;
    auto scaled = state.Update(100, matrix, 1.5f);
    assert(scaled.m[0][1] == 3 && scaled.m[1][0] == -3 && scaled.m[2][2] == 3);
    for (int axis=0;axis<4;++axis) assert(scaled.m[3][axis] == matrix.m[3][axis]);
    auto repeated = state.Update(100, scaled, 1.5f);
    assert(repeated.m[0][1] == 3);
    auto engineUpdate = state.Update(100, matrix, 1.5f);
    assert(engineUpdate.m[0][1] == 3);
    engineUpdate.m[3][0] = 90;
    auto reset = state.Update(100, engineUpdate, 1);
    assert(reset.m[0][1] == 2 && reset.m[3][0] == 90);
    auto replacement = state.Update(200, matrix, .5f);
    assert(replacement.m[0][1] == 1);
    matrix.m[0][0]=std::numeric_limits<float>::quiet_NaN(); assert(!SpatialSize::Valid(matrix));
    matrix={}; assert(!SpatialSize::Valid(matrix));
}
