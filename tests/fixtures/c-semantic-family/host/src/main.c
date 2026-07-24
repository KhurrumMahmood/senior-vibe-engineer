#include "csemantic/semantic.h"

#include <stdio.h>

int main(void)
{
    job value = {0};
    request_options old_options = options_straggler();
    request_options current_options = options_alpha();
    summary invoice = summarize_invoice(100);
    summary statement = build_statement(100);

    job_queue(&value);
    job_finish(&value);
    job_start(&value);
    (void)options_beta();
    (void)options_gamma();
    (void)invoice_preview(100);
    (void)statement_preview(100);
    (void)migrate_status(LEGACY_STATUS_PENDING);
    printf(
        "semantic:%s:%s:%d:%d:%s\n",
        value.state,
        current_options.region,
        invoice.subtotal + statement.tax + old_options.retries + current_options.retries,
        invoke_registered(0),
        legacy_wire_name()
    );
    return 0;
}
