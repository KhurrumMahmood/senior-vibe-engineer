#include "cppmove/invoice.hpp"

#include <iostream>

int main()
{
    std::cout << cppmove::render_invoice(cppmove::Invoice{42, false}) << '\n';
    return 0;
}
