import 'package:dart_d4_calls/shared.dart' as shared;

int compute(int value) => shared.finalize(value);

class Beta {
  int compute(int value) => shared.finalize(value) + 20;
}
