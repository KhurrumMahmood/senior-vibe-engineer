#include "cohort/billing.hpp"

namespace cohort {

bool operator==(const Invoice& left, const Invoice& right)
{
    return left.id == right.id;
}

int Ledger::total(int multiplier) const
{
    return amount_ * multiplier;
}

int Ledger::total(const char* mode) const
{
    return mode[0] == 'd' ? amount_ * 2 : amount_;
}

int Ledger::operator[](int offset) const
{
    return amount_ + offset;
}

}  // namespace cohort
