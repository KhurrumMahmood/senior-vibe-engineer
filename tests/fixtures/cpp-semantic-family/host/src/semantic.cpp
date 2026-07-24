#include "cppsemantic/semantic.hpp"

namespace cppsemantic {
namespace {

[[maybe_unused]] int dormant_adjustment(int amount)
{
    return amount + 7;
}

int registered_handler(int value)
{
    return value + 1;
}

using Callback = int (*)(int);
Callback registry[] = {registered_handler};

}  // namespace

int invoke_registered(int value)
{
    return registry[0](value);
}

void queue(Job& job)
{
    job.state = "queued";
}

void start(Job& job)
{
    job.state = "running";
}

void finish(Job& job)
{
    job.state = "done";
}

RequestOptions options_straggler()
{
    return RequestOptions{.retries = 1};
}

RequestOptions options_alpha()
{
    return RequestOptions{.region = "us", .retries = 1};
}

RequestOptions options_beta()
{
    return RequestOptions{.region = "us", .retries = 2};
}

RequestOptions options_gamma()
{
    return RequestOptions{.region = "us", .retries = 3};
}

Summary summarize_invoice(int cents)
{
    return Summary{.subtotal = cents, .tax = cents / 10};
}

Summary build_statement(int cents)
{
    return Summary{.subtotal = cents, .tax = cents / 10};
}

int invoice_preview(int cents)
{
    const Summary value = summarize_invoice(cents);
    return value.subtotal + value.tax;
}

int statement_preview(int cents)
{
    const Summary value = build_statement(cents);
    return value.subtotal + value.tax;
}

CanonicalStatus migrate_status(LegacyStatus value)
{
    return value;
}

#define LEGACY_STATUS_WIRE "LegacyStatus"

const char* legacy_wire_name()
{
    return LEGACY_STATUS_WIRE;
}

int overloaded(int value)
{
    return value + 10;
}

double overloaded(double value)
{
    return value + 0.5;
}

Score operator+(Score left, Score right)
{
    return Score{.value = left.value + right.value};
}

}  // namespace cppsemantic
