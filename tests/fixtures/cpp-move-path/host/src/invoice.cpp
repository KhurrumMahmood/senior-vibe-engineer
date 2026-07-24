#include "cppmove/invoice.hpp"

#include "invoice_internal.hpp"

namespace cppmove::detail {

const char* status_label(bool paid)
{
    return paid ? "paid" : "pending";
}

}  // namespace cppmove::detail

namespace cppmove {

std::string render_invoice(const Invoice& invoice)
{
    return "invoice:INV-" + std::to_string(invoice.id) + ":" +
           detail::status_label(invoice.paid);
}

}  // namespace cppmove
