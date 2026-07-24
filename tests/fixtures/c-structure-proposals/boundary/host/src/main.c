#include "cproposal/legacy.h"
#include "cproposal/billing.h"

#include <stdio.h>

int main(void)
{
    printf("c-structure:%d\n", load_credentials() + render_export() + billing_parse());
    return 0;
}
