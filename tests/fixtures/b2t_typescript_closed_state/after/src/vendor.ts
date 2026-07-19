import { JobState, type JobState as JobStateValue } from "./job-state.js";

export interface VendorJobPayload {
  state: "queued" | "running" | "done";
}

/** Named vendor wire boundary: upstream payload values remain literal here. */
export function decodeVendorJobState(payload: VendorJobPayload): JobStateValue {
  if (payload.state === "queued") { // noqa: no-stringly-state: vendor wire value
    return JobState.QUEUED;
  }
  if (payload.state === "running") { // noqa: no-stringly-state: vendor wire value
    return JobState.RUNNING;
  }
  return JobState.DONE;
}
