fn main() {
    println!("cargo:rustc-check-cfg=cfg(fixture_build)");
    println!("cargo:rustc-cfg=fixture_build");
}
