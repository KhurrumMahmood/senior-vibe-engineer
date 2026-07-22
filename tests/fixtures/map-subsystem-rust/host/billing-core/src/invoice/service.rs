#[derive(Debug, Default)]
pub struct InvoiceService;

impl InvoiceService {
    pub fn total_cents(&self, line_items: &[u64]) -> u64 {
        line_items.iter().sum()
    }
}
