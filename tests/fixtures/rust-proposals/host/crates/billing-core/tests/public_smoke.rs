#[test]
fn public_smoke_is_exact() {
    assert_eq!(billing_core::fixture_smoke(), "42:valid:40");
}
