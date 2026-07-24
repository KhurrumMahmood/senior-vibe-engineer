#include "cohort/billing.hpp"
#include "internal.h"

namespace cohort {

int billing_queued_total(int subtotal, int service_fee)
{
    const int total = subtotal + service_fee;
    if (total < 0) {
        return 0;
    }
    return total;
}

}  // namespace cohort
