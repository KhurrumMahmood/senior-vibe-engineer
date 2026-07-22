#ifndef CPILOT_INVOICE_H
#define CPILOT_INVOICE_H

#include <stddef.h>

typedef const char *(*invoice_labeler)(int invoice_id);

int invoice_render(
    int invoice_id,
    invoice_labeler labeler,
    char *output,
    size_t output_size
);

#endif
