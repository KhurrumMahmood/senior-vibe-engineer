int routeInvoice(int value) {
  var result = value;
  final positiveAndEven = value > 0 && value.isEven;
  final outsideExpectedRange = value < 0 || value > 100;
  if (positiveAndEven) result += 1;
  if (outsideExpectedRange) result -= 1;
  if (value == 1) result += 1;
  if (value == 2) result += 1;
  if (value == 3) result += 1;
  if (value == 4) result += 1;
  if (value == 5) result += 1;
  if (value == 6) result += 1;
  if (value == 7) result += 1;
  if (value == 8) result += 1;
  for (var index = 0; index < 1; index += 1) {
    result += index;
  }
  var rounds = 0;
  while (rounds < 1) {
    rounds += 1;
  }
  do {
    result += 0;
  } while (false);
  switch (value) {
    case 9:
      result += 9;
    case 10:
      result += 10;
    default:
      result += 0;
  }
  try {
    result += int.parse('$value');
  } on FormatException {
    result -= 1;
  }
  return result;
}

int Function(int) nestedClosureDecoy() {
  return (value) {
    if (value > 0) value += 1;
    if (value > 1) value += 1;
    if (value > 2) value += 1;
    if (value > 3) value += 1;
    if (value > 4) value += 1;
    if (value > 5) value += 1;
    if (value > 6) value += 1;
    if (value > 7) value += 1;
    if (value > 8) value += 1;
    if (value > 9) value += 1;
    if (value > 10) value += 1;
    if (value > 11) value += 1;
    if (value > 12) value += 1;
    if (value > 13) value += 1;
    if (value > 14) value += 1;
    if (value > 15) value += 1;
    if (value > 16) value += 1;
    if (value > 17) value += 1;
    if (value > 18) value += 1;
    return value;
  };
}

int localFunctionDecoy(int value) {
  int nested(int current) {
    if (current > 0) current += 1;
    if (current > 1) current += 1;
    if (current > 2) current += 1;
    if (current > 3) current += 1;
    if (current > 4) current += 1;
    if (current > 5) current += 1;
    if (current > 6) current += 1;
    if (current > 7) current += 1;
    if (current > 8) current += 1;
    if (current > 9) current += 1;
    if (current > 10) current += 1;
    if (current > 11) current += 1;
    if (current > 12) current += 1;
    if (current > 13) current += 1;
    if (current > 14) current += 1;
    if (current > 15) current += 1;
    if (current > 16) current += 1;
    if (current > 17) current += 1;
    if (current > 18) current += 1;
    return current;
  }

  return nested(value);
}
