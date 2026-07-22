import { JobState, type Job } from "../src/jobs.js";

const job: Job = { state: JobState.QUEUED };
export const testOnlyStateCheck = job.state === JobState.QUEUED;
