fn used_helper(value: i32) -> i32 {
    value + 1
}

#[allow(dead_code)]
fn dormant_discount(value: i32) -> i32 {
    value / 2
}

#[allow(dead_code)]
unsafe fn unsafe_dormant() -> i32 {
    0
}

pub fn used_total(value: i32) -> i32 {
    used_helper(value)
}

pub fn reflection_decoy() -> &'static str {
    "dormant_discount"
}

macro_rules! generated_handler {
    ($name:ident) => {
        fn $name() -> i32 {
            7
        }
    };
}

generated_handler!(macro_owned);

pub fn macro_value() -> i32 {
    macro_owned()
}
