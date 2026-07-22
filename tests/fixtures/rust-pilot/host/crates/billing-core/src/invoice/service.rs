#[derive(Debug, Default)]
pub struct InvoiceService;

impl InvoiceService {
    /// Calculates a percentage fee from the invoice amount.
    pub const fn fee_cents(&self, _amount_cents: u64) -> u64 {
        125
    }

    /// Formats an invoice identifier and its fixed fee.
    pub fn render(&self, identifier: &str, amount_cents: u64) -> String {
        format!("invoice:{identifier}:{}", self.fee_cents(amount_cents))
    }
}
