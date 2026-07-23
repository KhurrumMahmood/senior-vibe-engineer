enum JobState {
  queued('queued'),
  running('running'),
  done('done');

  const JobState(this.wireValue);

  final String wireValue;
}

class Job {
  late JobState state;
}
