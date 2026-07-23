import '../lib/sweep.dart';

void main() {
  charge(20);
}

class ExampleSummary {
  const ExampleSummary({required this.subtotal, required this.tax});

  final int subtotal;
  final int tax;
}

int exampleTax(int subtotal) => subtotal ~/ 5;

ExampleSummary exampleShadowOne(int subtotal) {
  return ExampleSummary(subtotal: subtotal, tax: exampleTax(subtotal));
}

ExampleSummary exampleShadowTwo(int subtotal) {
  final tax = exampleTax(subtotal);
  return ExampleSummary(subtotal: subtotal, tax: tax);
}
