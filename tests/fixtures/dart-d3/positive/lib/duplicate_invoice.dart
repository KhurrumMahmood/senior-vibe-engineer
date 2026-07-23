int normalizeInvoice(int value) {
  final adjusted = value + 1;
  final doubled = adjusted * 2;
  final bounded = doubled > 100 ? 100 : doubled;
  return bounded - 3;
}
