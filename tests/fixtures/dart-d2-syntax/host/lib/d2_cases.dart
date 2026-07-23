// decision:0001 line comment
/* decision:0001 block comment */
/// decision:0001 doc comment
void decisionAnchor() {}

// decision:9999 is intentionally orphaned.
const ordinaryString = '// decision:7000';
const rawString = r'/* decision:7001 */';
const multilineString = '''
/// decision:7002
/* decision:7003 */
''';
const interpolationText = 'value: $ordinaryString // decision:7004';
final interpolationComment = '${ /* decision:0001 */ ordinaryString}';

/// Returns a 10 percent rate based on the invoice amount.
int invoiceRate() => 125;

/// Returns the fixed 125 rate.
int matchingRate() {
  return 125;
}

/// Returns a 10 percent rate based on the invoice amount.
int computedRate(int amount) => amount ~/ 10;

/// Returns a 10 percent rate based on the invoice amount.
int closureRate() => (() => 125)();

/// Detached 10 percent note.

int detachedRate() => 125;

mixin RateMixin {
  /// Returns a 10 percent rate based on the invoice amount.
  int mixinRate() => 125;
}

extension RateExtension on int {
  /// Returns a 10 percent rate based on the invoice amount.
  int extensionRate() => 125;
}

String parseInvoice(String value) => value;

void standardSites() {
  /// Returns a 10 percent rate based on the invoice amount.
  int localRate() => 125;

  if (localRate() == 0) throw StateError('unreachable');
  try {
    parseInvoice('guarded');
  } catch (_) {}
  parseInvoice('gap');

  final tearOff = parseInvoice;
  const callText = "parseInvoice('string')";
  InvoiceParser().parseInvoice('receiver');
  if (tearOff(callText).isEmpty) {
    throw StateError('unreachable');
  }
}

final class InvoiceParser {
  String parseInvoice(String value) => value;
}
