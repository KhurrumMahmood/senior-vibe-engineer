use std::env;
use std::fs;
use std::path::PathBuf;

fn main() {
    println!("cargo:rerun-if-changed=build.rs");
    println!("cargo:rustc-check-cfg=cfg(fixture_build)");
    println!("cargo:rustc-cfg=fixture_build");

    let output =
        PathBuf::from(env::var_os("OUT_DIR").expect("OUT_DIR is set")).join("fixture_generated.rs");
    fs::write(
        output,
        "pub const GENERATED_MARKER: &str = \"build-script\";\n",
    )
    .expect("write generated fixture");
}
