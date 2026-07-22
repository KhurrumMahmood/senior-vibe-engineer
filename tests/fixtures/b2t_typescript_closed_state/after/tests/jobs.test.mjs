import assert from "node:assert/strict";
import test from "node:test";
import { JobState, isDone, isRunning, queue } from "../.test-dist/jobs.js";
import { decodeVendorJobState } from "../.test-dist/vendor.js";

test("closed state behavior", () => {
  const job = { state: JobState.RUNNING };
  assert.equal(isRunning(job), true);
  queue(job);
  assert.equal(isDone(job), false);
  assert.equal(decodeVendorJobState({ state: "queued" }), JobState.QUEUED);
});
