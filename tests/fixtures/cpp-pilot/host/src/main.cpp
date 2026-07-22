#include "cpppilot/invoice.hpp"

#include <iostream>

int main()
{
    std::cout << cpppilot::render_invoice(42, cpppilot::InvoiceStatus::pending)
              << '\n';
    return 0;
}
