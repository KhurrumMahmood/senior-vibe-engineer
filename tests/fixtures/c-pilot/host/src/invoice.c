#include "cpilot/invoice.h"

#include <stdio.h>

#include "invoice_internal.h"

// decision: keep the sequence translation-unit local to avoid public state.
static int invoice_sequence = 0;

int invoice_next_sequence(void)
{
    invoice_sequence += 1;
    return invoice_sequence;
}

int invoice_render(
    int invoice_id,
    invoice_labeler labeler,
    char *output,
    size_t output_size
)
{
    return snprintf(
        output,
        output_size,
        "invoice:%s:%d:%s",
        labeler(invoice_id),
        invoice_next_sequence(),
        CPILOT_MODE
    );
}
