pub fn quote_total(amount: u32) -> u32 {
    normalize(amount) + quote_fee()
}

pub fn quote_preview(amount: u32) -> u32 {
    normalize(amount)
}

pub fn quote_fee() -> u32 {
    2
}

pub(super) fn normalize(amount: u32) -> u32 {
    amount
}
