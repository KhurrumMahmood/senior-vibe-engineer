macro_rules! define_currency {
    ($name:ident) => {
        pub const $name: &str = stringify!($name);
    };
}

define_currency!(USD);

pub trait RuntimeLabel {
    fn label(&self) -> &'static str;
}

pub fn dynamic_label(value: &dyn RuntimeLabel) -> &'static str {
    value.label()
}
