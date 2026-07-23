class Invoice {
  const Invoice(this.subtotal);

  final int subtotal;
}

class InvoiceSummary {
  const InvoiceSummary({required this.subtotal, required this.tax});

  final int subtotal;
  final int tax;
}

int computeTax(int subtotal) => subtotal ~/ 5;

InvoiceSummary summarizeInvoice(Invoice invoice) {
  final subtotal = invoice.subtotal;
  final tax = computeTax(subtotal);
  return InvoiceSummary(subtotal: subtotal, tax: tax);
}

InvoiceSummary buildStatement(Invoice invoice) {
  final amountBeforeTax = invoice.subtotal;
  final calculatedTax = computeTax(amountBeforeTax);
  return InvoiceSummary(subtotal: amountBeforeTax, tax: calculatedTax);
}

InvoiceSummary protocolDecoy(Invoice invoice) {
  final subtotal = invoice.subtotal;
  final taxWithProtocolFee = computeTax(subtotal) + 1;
  return InvoiceSummary(subtotal: subtotal, tax: taxWithProtocolFee);
}

InvoiceSummary wrapperDuplicationDecoy(Invoice invoice) =>
    summarizeInvoice(invoice);
