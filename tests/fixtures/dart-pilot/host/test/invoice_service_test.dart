import '../lib/invoice_service.dart';

void main() {
  const service = InvoiceService();
  final actual = service.render((id: 'INV-42', cents: 125));
  if (actual != 'invoice:INV-42:125') {
    throw StateError('unexpected invoice rendering: $actual');
  }
  print('native-test:ok');
}
