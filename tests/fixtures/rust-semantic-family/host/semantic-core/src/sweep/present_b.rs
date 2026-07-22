use super::ChargeOptions;

pub fn options() -> ChargeOptions {
    ChargeOptions {
        amount: 20,
        audit: true,
    }
}
