use super::ChargeOptions;

pub fn options() -> ChargeOptions {
    ChargeOptions {
        amount: 10,
        audit: true,
    }
}
