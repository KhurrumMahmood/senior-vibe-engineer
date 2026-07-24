#include "cbilling/invoice.h"

#include <stdio.h>

int main(void)
{
    int total = billing_pending_total(10, 12);
    printf("c-lexical-smoke:%d\n", total);
    return 0;
}
