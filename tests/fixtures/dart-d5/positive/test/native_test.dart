import '../lib/state.dart';
import '../lib/sweep.dart';
import '../lib/duplication.dart';

void main() {
  final job = Job('new');
  job.queue();
  if (job.state != 'queued') throw StateError('unexpected state');
  if (charge(2, audit: true) != 3) throw StateError('unexpected charge');
  final invoice = Invoice(10);
  if (invoicePreview(invoice).tax != statementPreview(invoice).tax) {
    throw StateError('unexpected summary');
  }
}

class TestOnlyState {
  String state = 'queued';

  void run() {
    state = 'running';
    state = 'done';
  }
}

class TestSummary {
  const TestSummary({required this.subtotal, required this.tax});

  final int subtotal;
  final int tax;
}

int testTax(int subtotal) => subtotal ~/ 5;

TestSummary testShadowOne(int subtotal) {
  return TestSummary(subtotal: subtotal, tax: testTax(subtotal));
}

TestSummary testShadowTwo(int subtotal) {
  final tax = testTax(subtotal);
  return TestSummary(subtotal: subtotal, tax: tax);
}
