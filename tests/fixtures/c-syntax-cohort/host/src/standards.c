#include "cohort.h"

int parse_invoice(void)
{
    return 7;
}

int handled_parse(void)
{
    if (parse_invoice() > 0) {
        return 7;
    }
    return 0;
}

int unhandled_parse(void)
{
    return parse_invoice();
}

const char *call_shaped_string = "parse_invoice()";
