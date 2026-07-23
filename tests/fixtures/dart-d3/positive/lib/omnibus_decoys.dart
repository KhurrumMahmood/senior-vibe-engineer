mixin GhostInvoiceMixin {
  int loadGhostInvoice() => 1;
  int saveGhostInvoice() => 2;
  int loadGhostPayment() => 3;
  int saveGhostPayment() => 4;
  int loadGhostShipping() => 5;
  int saveGhostShipping() => 6;
  int loadGhostAudit() => 7;
  int saveGhostAudit() => 8;
}

extension GhostShippingExtension on String {
  int loadExtensionInvoice() => length;
  int saveExtensionInvoice() => length;
  int loadExtensionPayment() => length;
  int saveExtensionPayment() => length;
  int loadExtensionShipping() => length;
  int saveExtensionShipping() => length;
  int loadExtensionAudit() => length;
  int saveExtensionAudit() => length;
}

const omnibusStringDecoy =
    'loadStringInvoice saveStringInvoice loadStringPayment saveStringPayment '
    'loadStringShipping saveStringShipping loadStringAudit saveStringAudit';
