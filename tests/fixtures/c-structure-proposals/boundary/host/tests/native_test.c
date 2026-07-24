#include "cproposal/legacy.h"
#include "cproposal/billing.h"

#include <stdio.h>

int main(void)
{
    if (write_export() != 6 || load_invoice() != 8 || billing_validate() != 30) {
        return 1;
    }
    puts("c-structure-native:ok");
    return 0;
}
