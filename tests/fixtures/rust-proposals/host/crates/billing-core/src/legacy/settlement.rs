pub fn settle(amount: u32) -> u32 {
    super::quote::normalize(amount)
}

pub fn receipt(amount: u32) -> String {
    format!("settled:{amount}")
}

pub fn status() -> &'static str {
    "settled"
}
