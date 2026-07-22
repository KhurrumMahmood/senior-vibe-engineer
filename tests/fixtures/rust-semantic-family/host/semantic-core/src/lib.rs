pub mod dormant;
pub mod duplication;
pub mod rename;
pub mod state;
pub mod sweep;

pub fn smoke_value() -> i32 {
    dormant::used_total(10) + duplication::caller_a::invoice_total(20)
}
