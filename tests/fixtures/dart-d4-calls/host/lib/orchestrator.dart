import 'owners/alpha.dart' as alpha;
import 'package:dart_d4_calls/owners/beta.dart' as beta;

int orchestrate(int value) {
  final alphaWorker = alpha.Alpha();
  final betaWorker = beta.Beta();
  return alpha.compute(value) +
      beta.compute(value) +
      alphaWorker.compute(value) +
      betaWorker.compute(value);
}

int dynamicDispatch(dynamic worker, int value) => worker.compute(value);

String externalCall(int value) => value.toString();
