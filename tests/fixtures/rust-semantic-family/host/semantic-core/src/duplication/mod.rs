pub mod caller_a;
pub mod caller_b;

pub struct InvoiceSummary {
    pub subtotal: i32,
    pub tax: i32,
}

#[allow(clippy::derivable_impls)]
impl Default for InvoiceSummary {
    fn default() -> Self {
        Self {
            subtotal: 0,
            tax: 0,
        }
    }
}

pub fn summarize_invoice(value: i32) -> InvoiceSummary {
    let tax = value / 10;
    InvoiceSummary {
        subtotal: value,
        tax,
    }
}

pub fn build_statement(value: i32) -> InvoiceSummary {
    let subtotal = value;
    InvoiceSummary {
        subtotal,
        tax: subtotal / 10,
    }
}

pub fn wrapper_decoy(value: i32) -> InvoiceSummary {
    summarize_invoice(value)
}

pub fn policy_decoy(value: i32) -> InvoiceSummary {
    InvoiceSummary {
        subtotal: value,
        ..InvoiceSummary::default()
    }
}
