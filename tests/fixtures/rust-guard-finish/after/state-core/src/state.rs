#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum JobState {
    Queued,
    Running,
    Done,
}

impl JobState {
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Queued => "queued",
            Self::Running => "running",
            Self::Done => "done",
        }
    }
}

#[derive(Debug)]
pub struct Job {
    pub state: JobState,
}

pub struct OtherJob {
    pub status: String,
}

pub fn unrelated_display_value(job: &OtherJob) -> bool {
    job.status == "display"
}
