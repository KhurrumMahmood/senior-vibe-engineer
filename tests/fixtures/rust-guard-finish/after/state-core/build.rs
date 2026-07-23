fn main() {
    println!("cargo:rustc-check-cfg=cfg(fixture_extra)");
}
