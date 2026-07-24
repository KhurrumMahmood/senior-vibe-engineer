#include "cbilling/invoice.h"

#include <stdio.h>

int main(void)
{
    if (billing_pending_total(10, 12) != 132) {
        return 1;
    }
    if (billing_queued_total(10, 12) != 132) {
        return 2;
    }
    puts("c-native-test:ok");
    return 0;
}
