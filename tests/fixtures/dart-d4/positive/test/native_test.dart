import '../lib/core/service.dart';

void main() {
  if (publicValue(3) != 6) throw StateError('unexpected value');
}
