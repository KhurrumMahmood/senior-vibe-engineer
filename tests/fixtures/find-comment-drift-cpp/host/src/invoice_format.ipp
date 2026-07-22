#ifndef CPPPILOT_INVOICE_FORMAT_IPP
#define CPPPILOT_INVOICE_FORMAT_IPP

#include <sstream>
#include <string>
#include <string_view>

#include "format_support.inl"

inline std::string format_invoice(
    int invoice_id,
    std::string_view label,
    std::string_view mode
)
{
    std::ostringstream output;
    output << "invoice:" << label << invoice_separator << mode
           << invoice_separator << invoice_id;
    return output.str();
}

#endif
