import type { Job } from "../jobs.js";

export const fixtureIsQueued = (job: Job): boolean => job.state === "queued";
