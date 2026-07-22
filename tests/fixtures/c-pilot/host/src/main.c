#include "cpilot/invoice.h"

#include <stdio.h>

static const char *invoice_label(int invoice_id)
{
    (void)invoice_id;
    return "INV-42";
}

int main(void)
{
    char output[64];
    int rendered = invoice_render(42, invoice_label, output, sizeof(output));

    if (rendered < 0 || (size_t)rendered >= sizeof(output)) {
        return 2;
    }
    puts(output);
    return 0;
}
