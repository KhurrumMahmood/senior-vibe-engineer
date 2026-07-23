class Invoice {
  const Invoice(this.subtotal);

  final int subtotal;
}

class InvoiceSummary {
  const InvoiceSummary({required this.subtotal, required this.tax});

  final int subtotal;
  final int tax;
}

class CloneSummary {
  const CloneSummary({required this.subtotal, required this.tax});

  final int subtotal;
  final int tax;
}

int computeTax(int subtotal) => subtotal ~/ 5;

int policyFee(int subtotal) => subtotal == 0 ? 0 : 1;

InvoiceSummary summarizeInvoice(Invoice invoice) {
  final subtotal = invoice.subtotal;
  final tax = computeTax(subtotal);
  return InvoiceSummary(subtotal: subtotal, tax: tax);
}

InvoiceSummary buildStatement(Invoice invoice) {
  return InvoiceSummary(
    subtotal: invoice.subtotal,
    tax: computeTax(invoice.subtotal),
  );
}

InvoiceSummary protocolDecoy(Invoice invoice) {
  final subtotal = invoice.subtotal;
  final taxWithProtocolFee = computeTax(subtotal) + policyFee(subtotal);
  return InvoiceSummary(subtotal: subtotal, tax: taxWithProtocolFee);
}

InvoiceSummary wrapperDuplicationDecoy(Invoice invoice) =>
    summarizeInvoice(invoice);

InvoiceSummary genericDecoy<T extends Invoice>(T invoice) {
  return InvoiceSummary(
    subtotal: invoice.subtotal,
    tax: computeTax(invoice.subtotal),
  );
}

InvoiceSummary dynamicDecoy(dynamic invoice) {
  return InvoiceSummary(
    subtotal: invoice.subtotal as int,
    tax: computeTax(invoice.subtotal as int),
  );
}

class SummaryOwner {
  InvoiceSummary methodDecoy(Invoice invoice) {
    return InvoiceSummary(
      subtotal: invoice.subtotal,
      tax: computeTax(invoice.subtotal),
    );
  }
}

extension InvoiceSummaryExtension on Invoice {
  InvoiceSummary extensionDecoy() {
    return InvoiceSummary(subtotal: subtotal, tax: computeTax(subtotal));
  }
}

CloneSummary cloneOne(Invoice invoice) {
  final subtotal = invoice.subtotal;
  final tax = computeTax(subtotal);
  return CloneSummary(subtotal: subtotal, tax: tax);
}

CloneSummary cloneTwo(Invoice invoice) {
  final subtotal = invoice.subtotal;
  final tax = computeTax(subtotal);
  return CloneSummary(subtotal: subtotal, tax: tax);
}

InvoiceSummary invoicePreview(Invoice invoice) => summarizeInvoice(invoice);

InvoiceSummary statementPreview(Invoice invoice) => buildStatement(invoice);

InvoiceSummary protocolPreview(Invoice invoice) => protocolDecoy(invoice);

CloneSummary cloneOnePreview(Invoice invoice) => cloneOne(invoice);

CloneSummary cloneTwoPreview(Invoice invoice) => cloneTwo(invoice);
