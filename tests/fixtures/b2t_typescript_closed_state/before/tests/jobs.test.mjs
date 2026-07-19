import assert from "node:assert/strict";
import test from "node:test";
import { isDone, isRunning, queue } from "../.test-dist/jobs.js";

test("legacy state behavior", () => {
  const job = { state: "running" };
  assert.equal(isRunning(job), true);
  queue(job);
  assert.equal(isDone(job), false);
});
