#include "cohort/billing.hpp"

namespace cohort {

const char* billing_parse_legacy()
{
    return "cancelled_order";
}

int billing_pending_total(int subtotal, int service_fee)
{
    const int total = subtotal + service_fee;
    if (total < 0) {
        return 0;
    }
    return total;
}

}  // namespace cohort
