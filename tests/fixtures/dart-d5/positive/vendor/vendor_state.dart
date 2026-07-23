class VendorState {
  String state = 'queued';

  void run() {
    state = 'running';
    state = 'done';
  }
}
