import type { Job, JobState } from "./jobs.js";

export interface VendorJobPayload {
  state: JobState;
}

export function decodeVendorJobState(payload: VendorJobPayload): JobState {
  return payload.state === "queued" ? "queued" : payload.state; // noqa: no-stringly-state: vendor wire value
}

export function vendorFileFirstPartyCheck(job: Job): boolean {
  return job.state === "done"; // noqa: no-stringly-state: forged vendor claim
}
