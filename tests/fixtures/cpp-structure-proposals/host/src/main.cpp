#include "billing.hpp"
#include "legacy.hpp"

#include <iostream>

int main()
{
    std::cout << "cpp-structure:"
              << cppproposal::load_credentials() + cppproposal::render_export(2)
                     + cppproposal::billing_parse()
              << '\n';
    return 0;
}
