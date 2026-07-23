enum TypedPhase { queued, complete }

class Job {
  Job(this.state);

  String state;

  void queue() {
    state = 'queued';
  }

  void start() {
    state = 'running';
  }

  bool get isDone => 'done' == state;

  Map<String, Object> toJson() => {'state': state};
}

class TypedJob {
  TypedJob(this.phase);

  TypedPhase phase;
}

class LowEvidence {
  String status = 'queued';
}

String localStateDecoy() {
  var state = 'queued';
  state = 'running';
  return state;
}

class WirePayload {
  const WirePayload(this.state);

  final String state;

  Map<String, Object> toJson() => {'state': state};
}

void dynamicStateDecoy(dynamic payload) {
  payload.state = 'queued';
  if (payload.state == 'running') {
    payload.state = 'done';
  }
}
