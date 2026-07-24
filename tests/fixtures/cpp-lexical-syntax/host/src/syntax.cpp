#include "cohort/billing.hpp"

namespace cohort {

// decision:0001 keeps the direct syntax evidence bounded.
// decision:9999 is intentionally orphaned fixture evidence.
int route_invoice(int value)
{
    if (value == 1) { return 1; }
    if (value == 2) { return 2; }
    if (value == 3) { return 3; }
    if (value == 4) { return 4; }
    if (value == 5) { return 5; }
    if (value == 6) { return 6; }
    if (value == 7) { return 7; }
    if (value == 8) { return 8; }
    return 0;
}

int parse_invoice(int value)
{
    return value;
}

int handled_parse(int value)
{
    if (parse_invoice(value) > 0) {
        return 1;
    }
    return 0;
}

int unhandled_parse(int value)
{
    return parse_invoice(value);
}

}  // namespace cohort
