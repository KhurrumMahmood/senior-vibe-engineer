import 'package:dart_d7_clean/dart_d7_clean.dart';

void main() {
  if (describeCore(21) != 'core:42') {
    throw StateError('clean fixture changed');
  }
}
