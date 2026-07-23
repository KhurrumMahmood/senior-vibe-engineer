class OldLedger {
  const OldLedger(this.value);

  final int value;
}

class NewLedger {
  const NewLedger(this.value);

  final int value;
}

// OldLedger remains in migration prose until the rename review closes.
String describeLedger(NewLedger ledger) => 'new=${ledger.value}';
