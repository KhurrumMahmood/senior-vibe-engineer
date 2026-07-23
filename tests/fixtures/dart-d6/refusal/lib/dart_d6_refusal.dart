int meaningOfLife() => 42;

class _ExternalJob {
  late String state;

  void queue() {
    state = 'queued';
  }

  void start() {
    state = 'running';
  }

  bool get isDone => state == 'done';
}

Object externalStateDecoy() => _ExternalJob();
