class GeneratedState {
  String state = 'queued';

  void run() {
    state = 'running';
    state = 'done';
  }
}

class GeneratedSummary {
  const GeneratedSummary({required this.subtotal, required this.tax});

  final int subtotal;
  final int tax;
}

int generatedTax(int subtotal) => subtotal ~/ 5;

GeneratedSummary generatedShadowOne(int subtotal) {
  return GeneratedSummary(subtotal: subtotal, tax: generatedTax(subtotal));
}

GeneratedSummary generatedShadowTwo(int subtotal) {
  final tax = generatedTax(subtotal);
  return GeneratedSummary(subtotal: subtotal, tax: tax);
}
