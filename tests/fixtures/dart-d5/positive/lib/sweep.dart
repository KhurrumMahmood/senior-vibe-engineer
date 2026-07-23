int charge(int amount, {bool audit = false}) => audit ? amount + 1 : amount;

int wrapperDecoy(int amount) => charge(amount);

final chargeTearOff = charge;

extension IntCharge on int {
  int charge({bool audit = false}) => audit ? this + 1 : this;
}

int extensionDispatchDecoy() => 3.charge(audit: true);

int localCalleeDecoy() {
  int charge(int amount, {bool audit = false}) => amount;
  return charge(2);
}
