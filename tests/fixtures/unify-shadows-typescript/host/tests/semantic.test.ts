import assert from "node:assert/strict";
import test from "node:test";

import { summarizeByLoop, summarizeByReduction } from "../src/semantic.ts";

const entries = [
  { count: 2, label: "alpha" },
  { count: 3, label: "beta" },
];

test("the confirmed shadows preserve the same observable result", () => {
  const expected = { total: 5, labels: ["alpha", "beta"] };
  assert.deepEqual(summarizeByReduction(entries), expected);
  assert.deepEqual(summarizeByLoop(entries), expected);
});
