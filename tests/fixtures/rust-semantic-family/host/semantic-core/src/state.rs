#[derive(Debug)]
pub struct Job {
    pub state: String,
}

pub fn advance(job: &mut Job) -> bool {
    if job.state == "queued" {
        job.state = "running".to_owned();
    }
    job.state == "done"
}

#[derive(Debug, PartialEq)]
pub enum TypedPhase {
    Ready,
    Complete,
}

pub struct TypedJob {
    pub phase: TypedPhase,
}

pub struct LabelledThing {
    pub status: String,
}

pub fn single_label(thing: &LabelledThing) -> bool {
    thing.status == "display"
}
