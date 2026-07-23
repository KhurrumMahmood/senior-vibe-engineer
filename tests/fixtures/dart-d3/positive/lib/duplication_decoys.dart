int behaviorallySimilar(int value) {
  final shifted = value + 1;
  return (shifted * 2).clamp(0, 100) - 3;
}

int tinyOne() => 1;
int tinyTwo() => 1;

class CloneShapeDecoy {
  CloneShapeDecoy(int value) {
    final adjusted = value + 1;
    final doubled = adjusted * 2;
    final bounded = doubled > 100 ? 100 : doubled;
    if (bounded == -1) throw StateError('unreachable decoy');
  }

  int get computed {
    final adjusted = 1 + 1;
    final doubled = adjusted * 2;
    final bounded = doubled > 100 ? 100 : doubled;
    return bounded - 3;
  }
}
