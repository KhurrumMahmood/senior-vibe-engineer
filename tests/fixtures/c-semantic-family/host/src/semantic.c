#include "csemantic/semantic.h"

static int dormant_adjustment(int amount) __attribute__((unused));

static int dormant_adjustment(int amount)
{
    return amount + 7;
}

typedef int (*dispatch_fn)(int);

static int registered_handler(int value)
{
    return value + 1;
}

static dispatch_fn registry[] = {registered_handler};

int invoke_registered(int value)
{
    return registry[0](value);
}

void job_queue(job *value)
{
    value->state = "queued";
}

void job_start(job *value)
{
    value->state = "running";
}

void job_finish(job *value)
{
    value->state = "done";
}

request_options options_straggler(void)
{
    return (request_options){.retries = 1};
}

request_options options_alpha(void)
{
    return (request_options){.region = "us", .retries = 1};
}

request_options options_beta(void)
{
    return (request_options){.region = "us", .retries = 2};
}

request_options options_gamma(void)
{
    return (request_options){.region = "us", .retries = 3};
}

summary summarize_invoice(int cents)
{
    return (summary){.subtotal = cents, .tax = cents / 10};
}

summary build_statement(int cents)
{
    int tax = cents / 10;
    return (summary){.tax = tax, .subtotal = cents};
}

int invoice_preview(int cents)
{
    summary value = summarize_invoice(cents);
    return value.subtotal + value.tax;
}

int statement_preview(int cents)
{
    summary value = build_statement(cents);
    return value.subtotal + value.tax;
}

canonical_status migrate_status(legacy_status value)
{
    return value == LEGACY_STATUS_PENDING
        ? CANONICAL_STATUS_PENDING
        : CANONICAL_STATUS_PENDING;
}

#define LEGACY_STATUS_WIRE "legacy_status"

const char *legacy_wire_name(void)
{
    return LEGACY_STATUS_WIRE;
}
