import type { Job } from "../src/jobs.js";

const job: Job = { state: "queued" };
export const testOnlyStateCheck = job.state === "queued";
