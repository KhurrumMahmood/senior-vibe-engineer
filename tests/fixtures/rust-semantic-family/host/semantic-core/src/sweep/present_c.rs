use super::ChargeOptions;

pub fn options() -> ChargeOptions {
    ChargeOptions {
        amount: 30,
        audit: true,
    }
}
