#ifndef COHORT_BILLING_HPP
#define COHORT_BILLING_HPP

namespace cohort {

enum class BillingState { pending, paid };

struct Invoice {
    int id;
    const char* name;

    [[nodiscard]] const char* label() const { return name; }
};

[[nodiscard]] bool operator==(const Invoice& left, const Invoice& right);

class Ledger {
public:
    explicit Ledger(int amount) : amount_(amount) {}

    [[nodiscard]] int total(int multiplier) const;
    [[nodiscard]] int total(const char* mode) const;
    [[nodiscard]] int operator[](int offset) const;

private:
    int amount_;
};

template <typename T>
[[nodiscard]] int label_for(const T& value);

[[nodiscard]] const char* billing_parse_legacy();
[[nodiscard]] int billing_pending_total(int subtotal, int service_fee);
[[nodiscard]] int billing_queued_total(int subtotal, int service_fee);
[[nodiscard]] int route_invoice(int value);
[[nodiscard]] int handled_parse(int value);
[[nodiscard]] int unhandled_parse(int value);

}  // namespace cohort

#include "cohort/detail.tpp"

#endif
