import '../lib/d2_cases.dart';

void main() {
  if (invoiceRate() != 125 || parseInvoice('ok') != 'ok') {
    throw StateError('D2 fixture contract failed');
  }
  print('dart-d2-native:ok');
}
