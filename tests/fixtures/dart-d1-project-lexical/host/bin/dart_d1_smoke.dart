import '../lib/invoice_terms.dart';

void main() {
  if (normalizeOrder(' PAID ') != 'paid') {
    throw StateError('normalization failed');
  }
  print('dart-d1-ok');
}
