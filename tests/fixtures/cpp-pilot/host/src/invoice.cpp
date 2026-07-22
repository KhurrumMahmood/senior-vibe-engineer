#include "cpppilot/invoice.hpp"

#include "cpppilot/render.hpp"
#include "invoice_internal.hpp"

namespace cpppilot {
namespace detail {

// decision: keep label policy private to this translation unit.
const char* invoice_label(int id)
{
    return id == 42 ? "INV-42" : "INV-OTHER";
}

}  // namespace detail

std::string status_name(InvoiceStatus status)
{
    switch (status) {
    case InvoiceStatus::pending:
        return "pending";
    case InvoiceStatus::paid:
        return "paid";
    }
}

std::string render_invoice(const Invoice& invoice)
{
    return join_parts(
        "invoice:", detail::invoice_label(invoice.id()), ":",
        status_name(invoice.status()), ":", CPPPILOT_MODE
    );
}

std::string render_invoice(int id, InvoiceStatus status)
{
    return render_invoice(Invoice{id, status});
}

}  // namespace cpppilot
