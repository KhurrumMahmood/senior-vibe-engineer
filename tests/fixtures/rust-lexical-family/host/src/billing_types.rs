#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Invoice {
    pub identifier: String,
    pub amount_cents: u64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum InvoiceState {
    Pending,
    Paid,
}

type InternalSequence = u64;
