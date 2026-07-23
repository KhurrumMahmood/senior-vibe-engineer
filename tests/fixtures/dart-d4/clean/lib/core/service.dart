import 'models.dart';

int _used(int value) => value * 2;

int publicValue(int value) => _used(value);

NewLedger buildLedger(int value) => NewLedger(publicValue(value));
