#include "billing.hpp"
#include "legacy.hpp"

#include <iostream>
#include <string_view>

int main()
{
    if (cppproposal::render_export(std::string_view{"x"}) != 6
        || cppproposal::write_export() != 6 || cppproposal::billing_rule() != 20) {
        return 1;
    }
    std::cout << "cpp-structure-native:ok\n";
    return 0;
}
