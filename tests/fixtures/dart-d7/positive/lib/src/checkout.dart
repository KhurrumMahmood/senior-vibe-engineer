import 'billing_invoice.dart';
import 'billing_payment.dart';
import 'billing_tax.dart';
import 'invoicing/invoicing.dart';

String checkoutTotal(int subtotal) {
  const policy = InvoicePolicy();
  final calculator = InvoiceCalculator(policy);
  final billed = buildInvoice(calculator.total(subtotal));
  final paid = collectPayment(billed + calculateTax(subtotal));
  return formatInvoice(paid);
}
