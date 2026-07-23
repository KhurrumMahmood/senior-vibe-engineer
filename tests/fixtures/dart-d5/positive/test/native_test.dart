import '../lib/state.dart';
import '../lib/sweep.dart';

void main() {
  final job = Job('new');
  job.queue();
  if (job.state != 'queued') throw StateError('unexpected state');
  if (charge(2, audit: true) != 3) throw StateError('unexpected charge');
}

class TestOnlyState {
  String state = 'queued';

  void run() {
    state = 'running';
    state = 'done';
  }
}
