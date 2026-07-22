#[macro_export]
macro_rules! generated_label {
    ($value:expr) => {
        format!("generated:{}", $value)
    };
}

pub trait RuntimeLabel {
    fn label(&self) -> String;
}

pub fn label_through_trait(value: &dyn RuntimeLabel) -> String {
    value.label()
}
