use super::ChargeOptions;

pub fn options() -> ChargeOptions {
    ChargeOptions {
        amount: 40,
        ..ChargeOptions::default()
    }
}
