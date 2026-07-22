#ifndef CPPPILOT_INVOICE_HPP
#define CPPPILOT_INVOICE_HPP

#include <string>
#include <string_view>

#include "cpppilot/identity.tpp"

namespace cpppilot {

std::string render_invoice(int invoice_id, std::string_view label);

}  // namespace cpppilot

#endif
