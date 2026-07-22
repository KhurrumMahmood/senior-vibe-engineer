fn render(identifier: &str) -> String {
    format!("rustc:{identifier}:ok")
}

fn main() {
    println!("{}", render("INV-42"));
}

#[cfg(test)]
mod tests {
    use super::render;

    #[test]
    fn direct_rustc_test() {
        assert_eq!(render("INV-42"), "rustc:INV-42:ok");
    }
}
