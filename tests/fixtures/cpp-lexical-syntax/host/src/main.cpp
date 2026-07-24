#include "cohort/billing.hpp"

extern "C" int printf(const char*, ...);

int main()
{
    const cohort::Ledger ledger{5};
    printf("cpp-cohort:%d:%d\n", ledger.total(2), ledger[1]);
    return 0;
}
