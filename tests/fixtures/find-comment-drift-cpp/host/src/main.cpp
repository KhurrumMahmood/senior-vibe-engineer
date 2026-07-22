#include "cpppilot/invoice.hpp"
#include "cpppilot/ledger.hxx"
#include "cpppilot/roles.hh"

#include <iostream>
#include <string>

int main()
{
    const std::string comment_decoy = "// Return a different invoice label.";
    const std::string raw_comment_decoy = R"cpp(/* Return raw invoice. */)cpp";
    const std::string rendered = cpppilot::render_invoice(42, "INV-42");
    if (comment_decoy.empty() || raw_comment_decoy.empty()) {
        return 2;
    }
    std::cout << rendered << ':' << role_count() + ledger_size() << '\n';
    return 0;
}
