import type { JobState } from "./jobs.js";

export interface VendorJobPayload {
  state: JobState;
}

export function decodeVendorJobState(payload: VendorJobPayload): JobState {
  return payload.state === "queued" ? "queued" : payload.state;
}
