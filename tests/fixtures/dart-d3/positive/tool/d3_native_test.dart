import '../lib/public_surface.dart';

void main() {
  if (calculateInvoice(20) != 42) {
    throw StateError('Dart D3 native contract failed');
  }
}
