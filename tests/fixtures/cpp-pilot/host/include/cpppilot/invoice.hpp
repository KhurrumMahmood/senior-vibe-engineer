#ifndef CPPPILOT_INVOICE_HPP
#define CPPPILOT_INVOICE_HPP

#include <string>

namespace cpppilot {

enum class InvoiceStatus { pending, paid };

class Invoice final {
public:
    Invoice(int id, InvoiceStatus status) : id_(id), status_(status) {}

    [[nodiscard]] int id() const { return id_; }
    [[nodiscard]] InvoiceStatus status() const { return status_; }

private:
    int id_;
    InvoiceStatus status_;
};

[[nodiscard]] std::string status_name(InvoiceStatus status);
[[nodiscard]] std::string render_invoice(const Invoice& invoice);
[[nodiscard]] std::string render_invoice(int id, InvoiceStatus status);

}  // namespace cpppilot

#endif
