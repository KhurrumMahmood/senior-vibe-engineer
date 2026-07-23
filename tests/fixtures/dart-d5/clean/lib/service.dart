import 'models.dart';

int charge(int amount, {bool audit = false}) => audit ? amount + 1 : amount;

int callerA() {
  return charge(1, audit: true);
}

int callerB() {
  return charge(2, audit: true);
}

int callerC() {
  return charge(3, audit: true);
}

int callerD() {
  return charge(4, audit: true);
}

InvoiceSummary summarize(int value) => InvoiceSummary(value);

String describe(Job job) => job.phase.name;
