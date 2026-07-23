enum JobPhase { queued, running, done }

class Job {
  Job(this.phase);

  JobPhase phase;
}

class InvoiceSummary {
  const InvoiceSummary(this.total);

  final int total;
}
