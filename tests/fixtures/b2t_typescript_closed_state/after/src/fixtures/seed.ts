import { JobState, type Job } from "../jobs.js";

export const fixtureIsQueued = (job: Job): boolean => job.state === JobState.QUEUED;
