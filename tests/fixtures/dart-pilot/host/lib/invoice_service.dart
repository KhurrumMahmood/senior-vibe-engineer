typedef Invoice = ({String id, int cents});

final class InvoiceService {
  const InvoiceService();

  String render(Invoice invoice) => 'invoice:${invoice.id}:${invoice.cents}';
}
