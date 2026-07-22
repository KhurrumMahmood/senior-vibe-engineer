#[macro_export]
macro_rules! unrelated_label {
    ($value:expr) => {
        format!("label:{}", $value)
    };
}
