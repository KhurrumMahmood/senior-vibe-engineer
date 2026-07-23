import '../lib/service.dart';

void main() {
  if (callerD() != 5) throw StateError('unexpected value');
}
