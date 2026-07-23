import 'package:dart_d7_positive/dart_d7_positive.dart';

void main() {
  final actual = checkoutTotal(100);
  if (actual != 'invoice:116') {
    throw StateError('unexpected checkout total: $actual');
  }
}
