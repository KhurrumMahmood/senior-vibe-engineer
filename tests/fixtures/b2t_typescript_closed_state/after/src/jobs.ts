import { JobState, type JobState as JobStateValue } from "./job-state.js";

export { JobState } from "./job-state.js";
export type { JobState as JobStateValue } from "./job-state.js";

export interface Job {
  state: JobStateValue;
}

export function queue(job: Job): void {
  job.state = JobState.QUEUED;
}

export function isRunning(job: Job): boolean {
  return job.state === JobState.RUNNING;
}

export function isDone(job: Job): boolean {
  return JobState.DONE === job.state;
}
