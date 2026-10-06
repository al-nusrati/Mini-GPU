// ============================================================================
//  File    : sw/tests/check_types.cpp
//  Purpose : Prints C++ fixed-point conversions so tools/test_spec.py can
//            prove C++ and Python round EXACTLY the same way.
//  Input   : lines "type value" on stdin     Output: lines "type value raw"
//  Build   : g++ -std=c++17 -Isw/generated sw/tests/check_types.cpp -o check_types
// ============================================================================
#include "types.h"
#include <stdio.h>
#include <string.h>

int main()
{
    char type[32];
    double v;
    while (scanf("%31s %lf", type, &v) == 2) {
        long long raw;
        if      (strcmp(type, "pos")    == 0) raw = to_pos(v);
        else if (strcmp(type, "unit")   == 0) raw = to_unit(v);
        else if (strcmp(type, "screen") == 0) raw = to_screen(v);
        else if (strcmp(type, "grad")   == 0) raw = to_grad(v);
        else { printf("unknown type %s\n", type); return 1; }
        printf("%s %.17g %lld\n", type, v, raw);
    }
    return 0;
}
