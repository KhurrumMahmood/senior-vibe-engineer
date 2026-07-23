#[derive(Debug)]
pub struct Job {
    pub state: String,
}

impl Job {
    pub fn queued() -> Self {
        Self {
            state: "queued".to_owned(),
        }
    }
}

pub fn advance(job: &mut Job) -> bool {
    if job.state == "queued" {
        job.state = "running".to_owned();
    }
    job.state == "done"
}

pub struct OtherJob {
    pub status: String,
}

pub fn unrelated_display_value(job: &OtherJob) -> bool {
    job.status == "display"
}

pub trait StateLabel {
    fn state_label(&self) -> &str;
}

pub struct GenericJob<T> {
    pub state: T,
}

macro_rules! macro_state {
    () => {
        "macro-only"
    };
}

pub fn macro_value() -> &'static str {
    macro_state!()
}

#[cfg(fixture_extra)]
pub fn cfg_variant() -> &'static str {
    "cfg-only"
}

/// # Safety
/// The fixture never calls this function.
pub unsafe fn unsafe_state() -> &'static str {
    "unsafe-only"
}
