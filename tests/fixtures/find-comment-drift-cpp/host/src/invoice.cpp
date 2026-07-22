#include "cpppilot/invoice.hpp"

#include "common.h"
#include "invoice_detail.hpp"
#include "invoice_format.ipp"

namespace cpppilot {

std::string render_invoice(int invoice_id, std::string_view label)
{
    // Return invoice label.
    return format_invoice(identity(invoice_id), label, invoice_mode());
}

}  // namespace cpppilot
