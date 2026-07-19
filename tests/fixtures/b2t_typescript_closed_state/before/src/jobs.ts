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

export function isQueuedAlias(job: Job): boolean {
  const currentState = job.state;
  return currentState === "queued";
}

export function ensureQueued(job: Job): void {
  job.state ??= "queued";
}

export function queueBoth(primary: Job, backup: Job): void {
  primary.state = backup.state = "queued";
}
