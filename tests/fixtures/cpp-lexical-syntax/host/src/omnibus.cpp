#include "cohort/billing.hpp"

namespace cohort {

int invoice_load() { return 1; }
int invoice_save() { return 2; }
int receipt_load() { return 3; }
int receipt_save() { return 4; }
int customer_load() { return 5; }
int customer_save() { return 6; }
int ledger_load() { return 7; }
int ledger_save() { return 8; }

}  // namespace cohort
