export type JobState = "queued" | "running" | "done";

export interface Job {
  state: JobState;
}

export function queue(job: Job): void {
  job.state = "queued";
}

export function isRunning(job: Job): boolean {
  return job.state === "running";
}

export function isDone(job: Job): boolean {
  return "done" === job.state;
}
