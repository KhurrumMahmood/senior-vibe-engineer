import 'core/platform_stub.dart';
import 'package:dart_d4_positive/dart_d4_positive.dart';

String renderClient(int value) {
  final NewLedger ledger = buildLedger(value);
  void OldLedger() {}
  OldLedger();
  return '${describeLedger(ledger)} ${selectedPlatform()} selected';
}
