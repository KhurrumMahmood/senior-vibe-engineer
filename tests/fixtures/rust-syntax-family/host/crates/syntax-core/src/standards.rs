pub fn parse_invoice() -> Result<u8, &'static str> {
    Ok(7)
}

pub fn handled_parse() -> u8 {
    match parse_invoice() {
        Ok(value) if value > 0 => value,
        Ok(_) => 0,
        Err(_) => 1,
    }
}

pub fn unhandled_parse() {
    let _ = parse_invoice();
}

pub const CALL_SHAPED_STRING: &str = "parse_invoice()";
