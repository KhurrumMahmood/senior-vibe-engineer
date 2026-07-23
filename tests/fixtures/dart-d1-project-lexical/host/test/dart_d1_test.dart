import '../lib/invoice_terms.dart';

void main() {
  if (preferredOrderTerm != 'canceled_order') {
    throw StateError('preferred term changed');
  }
  if (normalizeOrder(' SENT ') != 'sent') {
    throw StateError('normalization failed');
  }
}
