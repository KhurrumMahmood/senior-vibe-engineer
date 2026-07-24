#include "cbilling/invoice.h"

int billing_state_code(billing_state state)
{
    if (state == BILLING_PAID) {
        return 200;
    }
    return 100;
}
