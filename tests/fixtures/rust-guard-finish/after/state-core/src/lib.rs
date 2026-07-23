pub mod state;

pub fn smoke_value() -> usize {
    state::JobState::Queued.as_str().len()
}
