import 'models.dart';

// ignore: unused_element
int _dormant(int value) => value + 99;

int _used(int value) => value * 2;

int _registered(int value) => value - 1;

int _tearOff(int value) => value + 1;

int publicValue(int value) => _used(value);

final callbacks = <int Function(int)>[_registered];
final retainedTearOff = _tearOff;

NewLedger buildLedger(int value) => NewLedger(publicValue(value));
