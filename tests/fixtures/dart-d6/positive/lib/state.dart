class Job {
  late String state;

  void queue() {
    state = 'queued';
  }

  void start() {
    state = 'running';
  }

  bool get isDone => state == 'done';

  Map<String, Object> toJson() => {'state': state};
}

class _PrivateJob {
  late String state;
}

Object privateStateDecoy() => _PrivateJob();
