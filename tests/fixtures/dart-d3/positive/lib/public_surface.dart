export 'src/reexported.dart';

typedef InvoiceMapper = String Function(int invoiceId);

enum PaymentState { pending, settled }

class InvoiceService {
  int total(int subtotal) => _adjust(subtotal);

  int _adjust(int subtotal) => subtotal + 2;
}

extension InvoiceFormatting on int {
  String asInvoiceLabel() => 'invoice-$this';

  // ignore: unused_element
  String _privateLabel() => 'private-$this';
}

int calculateInvoice(int subtotal) => _invoiceOffset(subtotal) * 2;

int _invoiceOffset(int subtotal) => subtotal + 1;

const declarationShapeString =
    'class StringDecoy {} enum StringState { fake } saveGhostInvoice';
