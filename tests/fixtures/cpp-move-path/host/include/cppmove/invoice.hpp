#pragma once

#include <string>

namespace cppmove {

struct Invoice final {
    int id;
    bool paid;
};

[[nodiscard]] std::string render_invoice(const Invoice& invoice);

}  // namespace cppmove
