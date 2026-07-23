class InvoicePolicy {
  const InvoicePolicy();

  int feeFor(int subtotal) => subtotal >= 100 ? 5 : 2;
}
