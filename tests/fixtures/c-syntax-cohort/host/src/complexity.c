#include "cohort.h"

#define MACRO_BRANCHES(value) ((value) > 0 && (value) < 100 || (value) == 200)

int route_invoice(int value)
{
    int score = value;
    if (value > 0) { score += 1; }
    if (value > 1) { score += 1; }
    if (value > 2) { score += 1; }
    if (value > 3) { score += 1; }
    if (value > 4) { score += 1; }
    if (value > 5) { score += 1; }
    if (value > 6) { score += 1; }
    if (value > 7) { score += 1; }
    (void)MACRO_BRANCHES(value);
    return score;
}

int route_invoice_wrapper(int value)
{
    return route_invoice(value);
}
