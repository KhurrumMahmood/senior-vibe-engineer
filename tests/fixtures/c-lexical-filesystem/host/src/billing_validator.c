#include "cbilling/invoice.h"

#include "billing_internal.h"

int billing_queued_total(int quantity, int unit_price)
{
    int subtotal = quantity * unit_price;
    int service_fee = subtotal / BILLING_FEE_DIVISOR;
    int adjusted = subtotal + service_fee;
    return adjusted > 0 ? adjusted : 0;
}

int billing_validator_code(int value)
{
    return value > 0 ? 1 : 0;
}
