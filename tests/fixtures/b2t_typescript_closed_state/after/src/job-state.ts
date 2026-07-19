export const JobState = {
  QUEUED: "queued",
  RUNNING: "running",
  DONE: "done",
} as const;

export type JobState = (typeof JobState)[keyof typeof JobState];
