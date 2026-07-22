pub fn route_invoice(value: u8) -> u8 {
    let mut score = value;
    if value > 0 {
        score += 1;
    }
    if value > 1 {
        score += 1;
    }
    if value > 2 {
        score += 1;
    }
    if value > 3 {
        score += 1;
    }
    if value > 4 {
        score += 1;
    }
    if value > 5 {
        score += 1;
    }
    if value > 6 {
        score += 1;
    }
    if value > 7 {
        score += 1;
    }
    if value > 8 {
        score += 1;
    }
    score
}

pub fn closure_decoy(value: u8) -> u8 {
    let deferred = |candidate: u8| {
        if candidate > 0 {
            return 1;
        }
        if candidate > 1 {
            return 2;
        }
        if candidate > 2 {
            return 3;
        }
        if candidate > 3 {
            return 4;
        }
        if candidate > 4 {
            return 5;
        }
        if candidate > 5 {
            return 6;
        }
        if candidate > 6 {
            return 7;
        }
        if candidate > 7 {
            return 8;
        }
        0
    };
    let _ = deferred;
    value
}
