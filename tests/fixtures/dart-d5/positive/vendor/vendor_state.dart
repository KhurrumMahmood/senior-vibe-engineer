class VendorState {
  String state = 'queued';

  void run() {
    state = 'running';
    state = 'done';
  }
}

class VendorSummary {
  const VendorSummary({required this.subtotal, required this.tax});

  final int subtotal;
  final int tax;
}

int vendorTax(int subtotal) => subtotal ~/ 5;

VendorSummary vendorShadowOne(int subtotal) {
  return VendorSummary(subtotal: subtotal, tax: vendorTax(subtotal));
}

VendorSummary vendorShadowTwo(int subtotal) {
  final tax = vendorTax(subtotal);
  return VendorSummary(subtotal: subtotal, tax: tax);
}
