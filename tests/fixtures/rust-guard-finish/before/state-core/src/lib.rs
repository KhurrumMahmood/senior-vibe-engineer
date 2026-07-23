pub mod state;

pub fn smoke_value() -> usize {
    state::Job::queued().state.len()
}
