import '../lib/orchestrator.dart';

void main() {
  if (orchestrate(1) != 36) throw StateError('unexpected call result');
}
