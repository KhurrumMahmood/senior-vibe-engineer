pub mod present_a;
pub mod present_b;
pub mod present_c;
pub mod straggler;

pub struct ChargeOptions {
    pub amount: i32,
    pub audit: bool,
}

#[allow(clippy::derivable_impls)]
impl Default for ChargeOptions {
    fn default() -> Self {
        Self {
            amount: 0,
            audit: false,
        }
    }
}

macro_rules! macro_options {
    () => {
        ChargeOptions {
            amount: 99,
            audit: false,
        }
    };
}

pub fn macro_owned_options() -> ChargeOptions {
    macro_options!()
}
