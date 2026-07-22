#[derive(Debug, Default, PartialEq, Eq)]
pub struct InvoiceService;

impl InvoiceService {
    pub const fn fee_cents(&self, _amount_cents: u64) -> u64 {
        125
    }

    pub fn render(&self, identifier: &str, amount_cents: u64) -> String {
        format!("invoice:{identifier}:{}", self.fee_cents(amount_cents))
    }
}
