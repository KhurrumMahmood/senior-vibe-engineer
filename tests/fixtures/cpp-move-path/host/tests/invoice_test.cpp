#include "cppmove/invoice.hpp"

#include <cassert>

int main()
{
    assert(cppmove::render_invoice(cppmove::Invoice{7, true}) ==
           "invoice:INV-7:paid");
    return 0;
}
