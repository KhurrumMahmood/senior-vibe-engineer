import 'policy.dart';

class InvoiceCalculator {
  const InvoiceCalculator(this.policy);

  final InvoicePolicy policy;

  int total(int subtotal) => subtotal + policy.feeFor(subtotal);
}
