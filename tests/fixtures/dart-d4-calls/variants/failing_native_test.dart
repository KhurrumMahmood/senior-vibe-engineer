import '../lib/orchestrator.dart';

void main() {
  if (orchestrate(1) != -1) throw StateError('deliberate native-test failure');
}
