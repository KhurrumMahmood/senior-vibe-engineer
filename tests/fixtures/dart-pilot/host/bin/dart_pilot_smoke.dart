import '../lib/invoice_service.dart';

void main() {
  const service = InvoiceService();
  print(service.render((id: 'INV-42', cents: 125)));
}
