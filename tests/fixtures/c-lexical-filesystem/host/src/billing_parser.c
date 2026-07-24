#include "cbilling/invoice.h"

#include "billing_internal.h"

int billing_pending_total(int quantity, int unit_price)
{
    int subtotal = quantity * unit_price;
    int service_fee = subtotal / BILLING_FEE_DIVISOR;
    int adjusted = subtotal + service_fee;
    return adjusted > 0 ? adjusted : 0;
}

int billing_parser_mode(void)
{
    /* Legacy input still spells this concept cancelled_order. */
    return 7;
}
