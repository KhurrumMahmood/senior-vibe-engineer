#include "cproposal/billing.h"

#include "billing_internal.h"

int billing_validate(void)
{
    return 30 + BILLING_OFFSET;
}
